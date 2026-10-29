"""Regression checks for refresh while projector output is open."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from main import Main
app = QApplication([])
w = Main()
w.external_output_window.show()
with patch.object(w, '_show_external_output') as reopen:
    for _ in range(5):
        w._refresh_external_screens()
    assert reopen.call_count == 0
assert w.external_output_window.isVisible()
with patch('main.available_audio_sources', side_effect=RuntimeError('device removed')):
    w._refresh_audio_sources()
assert not w._audio_refresh_in_progress
with patch('main.available_audio_sources', return_value=[]):
    w._refresh_audio_sources()
assert not w._audio_refresh_in_progress
with patch.object(w, '_screen_entries', side_effect=RuntimeError('display removed')):
    w._refresh_external_screens()
assert not w._display_refresh_in_progress
w._refresh_external_screens()
w.close()
print('PASS: repeated display refresh leaves output open; refresh recovers after device errors')
