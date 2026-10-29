"""Targeted offscreen regression checks; no audio/projector hardware required."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor, QPainter, QTransform
from PySide6.QtCore import QRectF, QTimer
from main import CanvasWidget, Main, ImagePreparationThread
app = QApplication([])
from PySide6.QtGui import QFontDatabase
QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
with tempfile.TemporaryDirectory() as directory:
    paths = []
    for name, color in [('a', 'red'), ('b', 'blue'), ('c', 'green')]:
        image = QImage(40, 40, QImage.Format_ARGB32)
        image.fill(QColor(color))
        path = str(Path(directory) / (name + '.png'))
        assert image.save(path)
        paths.append(path)
    canvas = CanvasWidget()
    canvas.resize(800, 600)
    assert canvas.projector_region() == QRectF(200, 150, 400, 300)
    assert canvas.import_image_variant(paths[0])[0]
    obj = canvas.objects[0]
    obj['transform'] = QTransform().translate(123, 234).rotate(17)
    stages = obj['stages']
    canvas._beat_slot = 2
    assert canvas.import_image_variant(paths[1])[0]
    assert len(canvas.objects) == 1 and canvas.objects[0] is obj
    assert obj['stages'] is stages and obj['transform'].dx() == 123
    assert canvas._beat_slot == 2
    assert all(not isinstance(v, QImage) for state in stages for v in state.values())
    assert canvas.import_background_image(paths[0], slot=0)[0]
    assert canvas.import_background_image(paths[1], slot=1)[0]
    bg = canvas.backgrounds[1]
    bg['stages'] = [canvas._make_stage_snapshot(bg['transform'], QColor('white'))]
    bg_stages = bg['stages']
    assert canvas.import_background_image(paths[2], slot=1)[0]
    assert len(canvas.backgrounds) == 2 and bg['stages'] is bg_stages
    assert canvas.import_background_image(paths[1], slot=1)[0]
    canvas.objects.clear()
    def render(mix):
        canvas.background_mix = mix
        image = QImage(320, 180, QImage.Format_ARGB32)
        painter = QPainter(image)
        canvas.render_scene(painter, QRectF(0, 0, 320, 180), False, False, projector=True)
        painter.end()
        return image.pixelColor(160, 90)
    assert render(0).red() > 250
    assert render(1).blue() > 250
    middle = render(.5)
    assert 120 <= middle.red() <= 135 and 120 <= middle.blue() <= 135
    # Verify only the central region is mapped, with no editor overlays.
    canvas.backgrounds.clear()
    seen = []
    canvas._draw_delete_fade = lambda p: seen.append(p.transform().mapRect(canvas.projector_region()))
    render(0)
    assert seen[-1] == QRectF(0, 0, 320, 180)
    received = []
    worker = ImagePreparationThread(paths[0], False)
    worker.prepared.connect(lambda result, error: received.append((result, error)))
    worker.start()
    while worker.isRunning():
        app.processEvents()
    worker.wait()
    app.processEvents()
    assert received and not received[0][1]
    # Build the real controls without opening physical audio devices.
    Main._finish_startup = lambda self: None
    main = Main()
    assert len(main.controls.background_slot_buttons) == 2
    main.controls.background_mix_slider.setValue(37)
    assert main.canvas.background_mix == .37
    # Exercise explicit Apply and cancel through the actual preparation UI.
    from unittest.mock import patch
    from PySide6.QtWidgets import QDialogButtonBox
    assert main.canvas.import_image_variant(paths[0])[0]
    original = main.canvas.objects[0]['core_image'].cacheKey()
    with patch('main.QFileDialog.getOpenFileName', return_value=(paths[1], '')):
        main._import_image_variant()
    while any(w.isRunning() for w in main._image_workers):
        app.processEvents()
    app.processEvents()
    assert main.canvas.objects[0]['core_image'].cacheKey() == original
    main._image_dialog.reject()
    assert main.canvas.objects[0]['core_image'].cacheKey() == original
    with patch('main.QFileDialog.getOpenFileName', return_value=(paths[1], '')):
        main._import_image_variant()
    while any(w.isRunning() for w in main._image_workers):
        app.processEvents()
    app.processEvents()
    main._image_dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Apply).click()
    assert main.canvas.objects[0]['source_path'] == paths[1]
    assert len(main._history) == 1
    main.canvas.import_background_image(paths[0], slot=0)
    main.canvas.import_background_image(paths[1], slot=1)
    main.controls.tabs.setCurrentWidget(main.controls.change_tab)
    main.controls.change_subtabs.setCurrentWidget(main.controls.change_background_subtab)
    main.show()
    app.processEvents()
    main.grab().save(str(Path(__file__).with_name('rai-refinement-preview.png')))
    main.close()
print('PASS: replacement state, bounded slots, blend endpoints/midpoint, projector crop, worker and UI smoke')
