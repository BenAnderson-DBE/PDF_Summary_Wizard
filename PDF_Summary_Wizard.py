import pymupdf
import datetime
import time
import tkinter as tk
from threading import Event, Thread
from tkinter import ttk
from tkinter import filedialog, messagebox, Text, scrolledtext
from pathlib import Path
from pymupdf import Point, Matrix, Rect, Quad

class MyRect(Rect):
    def expand_rect(self, pix=18):
        return MyRect(self[0] - pix, self[1] - pix, self[2] + pix, self[3] + pix)
    
    def center(self):
        return Point((self[0] + self[2]) / 2, (self[1] + self[3]) / 2)

    def fits_on_printer_paper(self):
        return ((min(self.width, self.height) < 6.75 * 72) and (max(self.width, self.height) < 9.25 * 72))
    
def merge_overlapping_rects(list_of_rects):
    final_rects = [list_of_rects.pop()]

    while len(list_of_rects) > 0:
        current_rect = list_of_rects.pop()
        sorted = False
        for final_rect in final_rects:
            if final_rect.intersects(current_rect):
                final_rect = final_rect.include_rect(current_rect)
                sorted = True
        if not sorted:
            final_rects.append(current_rect)
    
    return final_rects

class PlaceholderEntry(tk.Entry):
    def __init__(self, container, placeholder, color='grey', *args, **kwargs):
        super().__init__(container, *args, **kwargs)

        self.placeholder = placeholder
        self.placeholder_color = color
        self.default_fg_color = self['fg']

        self.bind("<FocusIn>", self._clear_placeholder)
        self.bind("<FocusOut>", self._add_placeholder)

        self._add_placeholder()

    def _add_placeholder(self, e=None):
        if not self.get():
            self.insert(0, self.placeholder)
            self.configure(fg=self.placeholder_color)

    def _clear_placeholder(self, e=None):
        if self.get() == self.placeholder:
            self.delete(0, tk.END)
            self.configure(fg=self.default_fg_color)

class WizardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Drawing File Processor Wizard")
        self.geometry("700x400")

        self.state_dict = dict()
        
        # Data storage to pass between pages
        self.selected_file = tk.StringVar()
        self.process_method = tk.StringVar(value="Summary")

        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True, padx=20, pady=20)

        self.page_rects = dict()

        # Start at the first page
        self.show_page(FileSelectionPage)

    def show_page(self, page_class):
        """Destroys current page and replaces it with the new one."""
        for widget in self.container.winfo_children():
            widget.destroy()
        
        page = page_class(self.container, self)
        page.pack(fill="both", expand=True)

# --- Page 1: File Selection ---
class FileSelectionPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Select a File", font=("Arial", 12, "bold")).pack(pady=10)
        
        self.file_label = tk.Label(self, text="No file selected", fg="gray", justify="right")
        self.file_label.pack(pady=5)

        ttk.Button(self, text="Browse...", command=self.browse_file).pack(pady=10)
        
        # Navigation
        ttk.Button(self, text="Next >", command=self.next_step).pack(side="bottom", anchor="e")

    def browse_file(self):
        filename = filedialog.askopenfilename()
        if filename:
            self.controller.selected_file.set(filename)
            self.controller.state_dict['chosen_file'] = filename
            self.file_label.config(text='.../' + '/'.join(filename.split("/")[-2:]), fg="black")

    def next_step(self):
        if not self.controller.selected_file.get():
            messagebox.showwarning("Error", "Please select a file first!")
        elif self.controller.selected_file.get().split(".")[-1].lower() != "pdf":
            messagebox.showwarning("Error", "The file you've selected is not a PDF. Please select another file.")
        else:
            self.controller.show_page(ImportingAnnotations)

class ImportingAnnotations(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Importing annotations...", font=("Arial", 12, "bold")).pack(pady=10)

        # Navigation
        self.next = ttk.Button(self, text="Next >", command=self.next_step)
        self.next.pack(side="bottom", anchor="e")
        self.next["state"] = "disabled"
        
        # self.console = tk.Text(self, font=("Helvetica", 10), wrap="word", height=100, width=200, state='disabled')
        # # self
        # self.console.pack(padx=10, pady=12)
        self.progress = ttk.Progressbar(self, orient="horizontal", length = 500, mode="determinate")
        self.progress.pack(pady=20)


        time.sleep(0.2)
        total_doc_annots = self.find_all_annots_in_pdf(self.controller.state_dict['chosen_file'])
        
        self.controller.state_dict["doc_annots"] = total_doc_annots
        
        time.sleep(0.2)
        self.next["state"] = "normal"
        tk.Label(self, text = "Done!", font=("Arial", 12, "bold")).pack(pady=10)
        time.sleep(0.3)

        self.controller.show_page(FilterAnnotations)
    
    # def finish(self):
    #     file = self.controller.selected_file.get()
    #     action = self.controller.process_method.get()
    #     messagebox.showinfo("Processing", f"Processing {file}\nUsing method: {action}")
    #     self.controller.destroy()

    def next_step(self):
        self.controller.show_page(FilterAnnotations)

    def find_all_annots_in_pdf(self, file_path):
        try:
            self.controller.doc = pymupdf.open(file_path)
        except Exception as e:
            print(f"Big issue arrose: {e}")
            raise e
        
        total_pages = self.controller.doc.page_count

        total_doc_annots = []
        
        for page_number in range(total_pages):
            self.progress.configure(value= ((page_number * 100) // total_pages))

            page = self.controller.doc[page_number]

            self.controller.page_rects[page_number] = page.rect

            annots = list(page.annots())
            print(page.number)


            if len(annots) > 0:
                print(f"pg. {page.number + 1} - {annots[0].info['content']=}")


                for annot in annots:
                    annot_dict = dict()
                    annot_dict["page_no"] = page_number
                    annot_dict["page_label"] = page.get_label()
                    annot_dict["id"] = annot.info['id']
                    annot_dict["author"] = annot.info['title']
                    annot_dict["stroke_color"] = annot.colors['stroke']

                    modif_time = datetime.datetime.strptime(annot.info['modDate'].replace("'", ""), r"D:%Y%m%d%H%M%S%z")

                    annot_dict["last_modified"] = modif_time
                    
                    annot_dict["raw_annot"] = annot

                    total_doc_annots.append(annot_dict)

        return total_doc_annots


# --- Page 3: Processing Options ---
class FilterAnnotations(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        tk.Label(self, text="Filter document annotations", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(self, text="Click [next] without selecting any filters to export all filters.", fg="gray", justify="left").pack(pady=5)

        # self.all_elements = [
        #     {"id": 1, "author": "Alice", "date": "2023-01-01", "page": 5},
        #     {"id": 2, "author": "Bob", "date": "2023-02-15", "page": 12},
        #     {"id": 3, "author": "Alice", "date": "2023-03-10", "page": 2},
        #     {"id": 4, "author": "Charlie", "date": "2023-01-20", "page": 45},
        # ]

        self.all_elements = self.controller.state_dict["doc_annots"]
        # Dict of the layout: {"page_no", "page_label", "id", "author", "last_modified", "raw_annot"}

        # Sidebar (Left) and Results (Right)
        self.sidebar = tk.Frame(self, width=200, bg="#f0f0f0", padx=10, pady=10)
        self.sidebar.pack(side="left", fill="y")

        self.main_area = tk.Frame(self, padx=10, pady=10)
        self.main_area.pack(side="right", fill="both", expand=True)

        # (Author Dropdown)
        tk.Label(self.sidebar, text="Filter by Author:", bg="#f0f0f0").pack(anchor="w")
        self.author_var = tk.StringVar(value="All")
        authors = ["All"] + list(set(e["author"] for e in self.all_elements))
        self.author_menu = ttk.Combobox(self.sidebar, textvariable=self.author_var, values=authors)
        self.author_menu.pack(fill="x", pady=5)
        self.author_menu.bind("<<ComboboxSelected>>", self.apply_filters)

        # (Page Dropdown)
        tk.Label(self.sidebar, text="Page number: (default all)", bg="#f0f0f0").pack(anchor="w")
        self.page_selection = PlaceholderEntry(self.sidebar, placeholder="e.g. 2-6, 9, 12-16")
        self.page_selection.pack(fill="x", pady=5)
        self.page_selection.bind("<FocusOut>", self.apply_filters)

        # Results Table (Treeview)
        self.tree = ttk.Treeview(self.main_area, columns=("page_no", "page_label", "author", "last_modified"), show="headings")
        self.tree.heading("#0", text="Color Sample")
        self.tree.heading("page_no", text="#")
        self.tree.heading("page_label", text="Page Label")
        self.tree.heading("author", text="Author")
        self.tree.heading("last_modified", text="Date Modified")

        self.tree.column("#0", width=40, minwidth=40, stretch=tk.NO)
        self.tree.column("page_no", width=40, minwidth=40, stretch=tk.NO)

        self.tree.pack(fill="both", expand=True)

        
        tk.Button(self.main_area, text="Next", command=self.next_step, bg="green", fg="white").pack(side="right", pady=10)
        tk.Button(self.main_area, text="< Back", command=lambda: controller.show_page(FileSelectionPage)).pack(side="right", pady=10)

        # Initial data load
        self.apply_filters()

    def apply_filters(self, event=None):
        # Clear the current view
        self.image_list = []
        for item in self.tree.get_children():
            self.tree.delete(item)

        selected_author = self.author_var.get()
        
        page_filter_text = self.page_selection.get()


        if "e.g." in page_filter_text:
            page_filter = "all"
        else:
            page_filter = set()
            for statement in page_filter_text.split(","):
                if "-" in statement:
                    low = statement.split("-")[0]
                    high = statement.split("-")[0]
                    [page_filter.add(i) for i in range(int(low), int(high) + 1)]
                else:
                    page_filter.add(int(statement))
        

        # Filter and Re-insert
        for elem in self.all_elements:
            img = tk.PhotoImage(width=16, height=16)
            if len(elem["stroke_color"]) != 0:
                r,g,b = (int(channel * 255) for channel in elem["stroke_color"])
                # print(elem["stroke_color"])
                color = f"#{r:02x}{g:02x}{b:02x}"
            else:
                color = "#FFFFFF"

            img.put(color, to=(0,0,16,16))

            self.image_list.append(img)

            if (selected_author == "All" or elem["author"] == selected_author) and (page_filter == "all" or int(elem["page_no"]) in page_filter):
                self.tree.insert("", "end",image=img, values=(elem["page_no"], elem["page_label"], elem["author"], elem["last_modified"]))


    def next_step(self):
        self.controller.state_dict["filtered_doc_annots"] = []
        
        selected_author = self.author_var.get()
        
        page_filter_text = self.page_selection.get()


        if "e.g." in page_filter_text:
            page_filter = "all"
        else:
            page_filter = set()
            for statement in page_filter_text.split(","):
                if "-" in statement:
                    low = statement.split("-")[0]
                    high = statement.split("-")[0]
                    [page_filter.add(i) for i in range(int(low), int(high) + 1)]
                else:
                    page_filter.add(int(statement))

        for elem in self.all_elements:
            if (selected_author == "All" or elem["author"] == selected_author) and (page_filter == "all" or int(elem["page_no"]) in page_filter):
                self.controller.state_dict["filtered_doc_annots"].append(elem)

        self.controller.show_page(GeneratingScreenshots)

class GeneratingScreenshots(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Generating PDF output...", font=("Arial", 12, "bold")).pack(pady=10)

        self.progress = ttk.Progressbar(self, orient="horizontal", length = 500, mode="determinate")
        self.progress.pack(pady=20)

        self.next = tk.Button(self, text="Next", command=self.finish, bg="green", fg="white")
        self.next.pack(side="right")
        self.next["state"] = "disabled"

        time.sleep(0.2)
        total_doc_screenshots = self.generate_output()
        
        # self.controller.state_dict["total_doc_screenshots"] = total_doc_screenshots
        
        time.sleep(0.2)
        # self.next["state"] = "normal"
        tk.Label(self, text = "Writing output pdf...", font=("Arial", 12, "bold")).pack(pady=10)
        time.sleep(0.3)

        self.write_output(total_doc_screenshots)

        time.sleep(0.2)
        tk.Label(self, text = "Done!", font=("Arial", 12, "bold")).pack(pady=10)
        time.sleep(5)

        self.finish()


    def finish(self):
        file = self.controller.selected_file.get()
        messagebox.showinfo("Summary generated", f"Input file {file}\nOutput file: {self.controller.state_dict['chosen_file'].split('.pdf')[0]}_summary.pdf")
        self.controller.destroy()

    def generate_output(self):
        filtered_annots = self.controller.state_dict["filtered_doc_annots"]
        total_doc_screenshots = []

        unique_pages = {annot['page_no'] for annot in filtered_annots}
        unique_annot_ids = {annot['id'] for annot in filtered_annots}
        total_pages = len(unique_pages)

        for page_number in unique_pages:
            page = self.controller.doc[page_number]
            all_annots = list(page.annots())

            self.progress.configure(value= ((page_number * 50) // total_pages))

            annots = []

            for annot in all_annots:
                if annot.info['id'] in unique_annot_ids:
                    annots.append(annot)
                # annot_dict["id"] = annot.info['id']

            # for annot in annots:
                
            rect_groups = [[annots[0]]]

            # Group together annotations that are close to each other
            for i in range(1,len(annots)):
                annot = annots[i]
                added_to_group = False
                annot_rect = MyRect(annot.apn_bbox)

                for j in range(len(rect_groups)):
                    group = rect_groups[j]
                    for k in range(len(group)):
                        rect = MyRect(group[k].apn_bbox)

                        if annot_rect.expand_rect().intersects(rect.expand_rect()):
                            group.append(annot)
                            k = len(group) + 1
                            j = len(rect_groups) + 10
                
                if j != len(rect_groups) + 10:
                    rect_groups.append([annot])

            # Make boundary rects that include all annots within their boundaries
            boundary_rects = []
            for rect_group in rect_groups:
                surrounding_rect = MyRect(rect_group[0].apn_bbox)

                if len(rect_group) > 0:
                    for i in range(1, len(rect_group)):
                        surrounding_rect = surrounding_rect.include_rect(rect_group[i].apn_bbox)
                    
                boundary_rects.append(surrounding_rect.expand_rect())

            # Make a really immature grouping of annotations
            screenshot_rects = boundary_rects.copy()

            for i in range(30):
                for j in range(len(screenshot_rects)):
                    if screenshot_rects[j].fits_on_printer_paper():
                        screenshot_rects[j] = screenshot_rects[j].expand_rect(pix=8)
                
                screenshot_rects = merge_overlapping_rects(screenshot_rects)

            final_number = len(screenshot_rects)

            screenshot_rects = boundary_rects.copy()
            while len(screenshot_rects) > final_number:
                
                for j in range(len(screenshot_rects)):
                    if screenshot_rects[j].fits_on_printer_paper():
                        screenshot_rects[j] = screenshot_rects[j].expand_rect(pix=3).intersect(self.controller.page_rects[page_number])
                
                screenshot_rects = merge_overlapping_rects(screenshot_rects)

            # Make a dictionary containing all the annotations and key information for this page
            screenshot_dict = {rect: {"annot_ids": [], "authors": set(), "last_modified": -1, "portrait": True} for rect in screenshot_rects}


            for annot in annots:
                for screenshot_rect in screenshot_dict.keys():
                    if annot.apn_bbox.intersects(screenshot_rect):
                        screenshot_dict[screenshot_rect]["annot_ids"].append(annot.info['id'])
                        screenshot_dict[screenshot_rect]["authors"].add(annot.info['title'])

                        modif_time = datetime.datetime.strptime(annot.info['modDate'].replace("'", ""), r"D:%Y%m%d%H%M%S%z")

                        if screenshot_dict[screenshot_rect]["last_modified"] == -1 or modif_time.timestamp() > screenshot_dict[screenshot_rect]["last_modified"].timestamp():
                            screenshot_dict[screenshot_rect]["last_modified"] = modif_time

                        if screenshot_rect.width > screenshot_rect.height:
                            screenshot_dict[screenshot_rect]["portrait"] = False

            total_doc_screenshots.append((page_number, page.get_label(), screenshot_dict))
            # print(total_doc_screenshots)
        return total_doc_screenshots
    
    def write_output(self,total_doc_screenshots):
        page_size = pymupdf.paper_sizes()['letter']
        output = pymupdf.open()

        i = 0
        
        for page_no,page_label,screenshot_dict in total_doc_screenshots:
            i += 0
            self.progress.configure(value= (50 + (i * 50) // len(total_doc_screenshots)))

            image_number = 0
            for screenshot in screenshot_dict.keys():
                image_number += 1

                # screenshot_dict[screenshot]["authors"]
                # screenshot_dict[screenshot]["last_modified"]
                # screenshot_dict[screenshot]["portrait"]

                if screenshot_dict[screenshot]["portrait"]:
                    new_page = output.new_page(width=page_size[0], height=page_size[1])
                else:
                    new_page = output.new_page(width=page_size[1], height=page_size[0])

                new_page.insert_image(Rect((36,36),screenshot.width, screenshot.height), pixmap = self.controller.doc[page_no].get_pixmap(clip=screenshot,dpi=72))

                r = pymupdf.Rect(30, min(screenshot.height + 10, new_page.mediabox[3] - 106), 210, 80)

                # new_page.draw_rect(r, color=[1,1,1], fill=[1,1,1])

                new_page.insert_text((36, min(screenshot.height + 20, new_page.mediabox[3] - 96)), f"{page_label}, image {image_number} of {len(screenshot_dict.keys())}")
                new_page.insert_text((36, min(screenshot.height + 40, new_page.mediabox[3] - 76)), f"Annotation author: {', '.join(screenshot_dict[screenshot]['authors'])}")
                new_page.insert_text((36, min(screenshot.height + 60, new_page.mediabox[3] - 56)), f"Annotation date: {screenshot_dict[screenshot]['last_modified'].strftime('%Y-%m-%d')}")

        output.save(self.controller.state_dict['chosen_file'].split(".pdf")[0] + "_summary.pdf")

# --- Page 2: Processing Options ---
class ProcessingOptionsPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Step 2: Choose Action", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(self, text=f"File: {self.controller.selected_file.get()[:30]}...").pack()

        options = ["Summary Report", "Convert to CSV", "Clean Data"]
        for opt in options:
            tk.Radiobutton(self, text=opt, variable=self.controller.process_method, value=opt).pack(anchor="w")

        # Navigation
        btn_frame = tk.Frame(self)
        btn_frame.pack(side="bottom", fill="x")
        
        tk.Button(btn_frame, text="< Back", command=lambda: controller.show_page(FileSelectionPage)).pack(side="left")
        tk.Button(btn_frame, text="Next", command=self.finish, bg="green", fg="white").pack(side="right")

    def finish(self):
        file = self.controller.selected_file.get()
        action = self.controller.process_method.get()
        self.controller.destroy()

if __name__ == "__main__":
    app = WizardApp()
    app.mainloop()