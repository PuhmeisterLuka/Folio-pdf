# Folio PDF

A small desktop app for everyday PDF work. Merge, split, compress, rotate and reorder pages, batch process whole folders, export pages as images, and convert Word documents to PDF. Everything runs locally, nothing leaves your machine.

I got tired of uploading documents to random PDF websites just to merge two files, so I made a local app for it.

Built with Python and CustomTkinter. Made on macOS, should run on Windows too but gets less testing there.

<img width="1102" height="749" alt="Merge screen" src="https://github.com/user-attachments/assets/5987a366-cee6-4078-baa0-72b2d5c8349b" />

## What it does

- **Merge**: combine PDFs in any order, reorder the list before saving
- **Split**: by page ranges, by clicking thumbnails, or one file per page
- **Compress**: three levels, medium and high also recompress embedded images

  <img width="1102" height="749" alt="Compress screen" src="https://github.com/user-attachments/assets/3d212c28-9246-4e5a-b197-42f1b12ebee5" />

- **Rotate and reorder**: drag pages around a thumbnail grid, rotate one page or all of them
- **Batch**: run compress, rotate or image export on a whole folder, or merge it into one PDF
- **PDF to image**: PNG or JPG at 72, 150 or 300 dpi

  <img width="1102" height="746" alt="Export to image screen" src="https://github.com/user-attachments/assets/cbf684a9-b0c6-4ffd-bf0b-88f4b68b6c8f" />

- **Word to PDF**: goes through Microsoft Word itself, so the output looks exactly like it does in Word

## Running from source

You need Python 3.11 or newer with tkinter. The python.org installer includes it. Homebrew Python does not, so on a Homebrew setup run `brew install python-tk` first.
