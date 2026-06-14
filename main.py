"""Entry point: python main.py"""

import tkinter as tk

from app import PLIIDEApp


def main():
    root = tk.Tk()
    PLIIDEApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
