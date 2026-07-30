import sys
from PySide6.QtWidgets import QApplication
from vispy import app as vispy_app

from viewmodels.main_viewmodel import MainViewModel
from views.main_window import MainWindow


def main():
    vispy_app.use_app("pyside6")
    qt_app = QApplication(sys.argv)

    view_model = MainViewModel()
    window = MainWindow(view_model)
    window.show()

    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())