"""GUI tests (display-free: only paths that never open a window)."""

from list2audio.gui.app import main as gui_main


def test_gui_version_no_window(capsys):
    assert gui_main(["--version"]) == 0
    assert "1.0.0" in capsys.readouterr().out
