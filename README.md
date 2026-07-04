# Folio PDF

A small desktop app for everyday PDF work. Merge, split, compress, rotate and reorder pages, batch process whole folders, export pages as images, and convert Word documents to PDF. Everything runs locally, nothing leaves your machine.

I got tired of uploading documents to random PDF websites just to merge two files, so I made a local app for it.

Built with Python and CustomTkinter. Made on macOS, should run on Windows too but gets less testing there.

<img width="1102" height="749" alt="compress copy" src="https://github.com/user-attachments/assets/3d212c28-9246-4e5a-b197-42f1b12ebee5" />


## What it does

- Merge: combine PDFs in any order, reorder the list before saving
- Split: by page ranges, by clicking thumbnails, or one file per page
- Compress: three levels, medium and high also recompress embedded images
- Rotate and reorder: drag pages around a thumbnail grid, rotate one page or all of them
- Batch: run compress, rotate or image export on a whole folder, or merge it into one PDF
- PDF to image: PNG or JPG at 72, 150 or 300 dpi
- Word to PDF: goes through Microsoft Word itself, so the output looks exactly like it does in Word

## Running from source

You need Python 3.11 or newer with tkinter. The python.org installer includes it. Homebrew Python does not, so on a Homebrew setup run `brew install python-tk` first.

```
git clone https://github.com/PuhmeisterLuka/folio-pdf.git
cd folio-pdf
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Building the macOS app

```
source venv/bin/activate
bash build.sh
```

The bundle ends up in `dist/Folio PDF.app`. The script also patches the app's Info.plist so macOS shows the automation permission prompt that Word to PDF needs, and so the app refuses to launch twice.

Building only works on a Mac, PyInstaller doesn't cross compile.

## Notes

- Word to PDF needs Microsoft Word installed. On first use macOS will ask if Folio PDF may control Word. Say yes, the conversion doesn't work without it.
- Your theme choice is saved to `~/.foliopdf_prefs.json`.
- The sidebar icons are [Feather icons](https://feathericons.com), rendered to PNG with `setup_icons.py`.

## Project layout

```
core/     the actual PDF operations, no UI code in here
ui/       CustomTkinter screens and shared widgets
assets/   icons and the app logo
```
