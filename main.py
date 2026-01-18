import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import sys

class PotholeLabeler:
    def __init__(self, root):
        self.root = root
        self.root.title("FastLabel - Universal Image Annotation")
        self.root.geometry("1200x800")

        # State
        self.image_dir = ""
        self.image_list = []
        self.current_idx = 0
        self.current_image = None  # PIL Image
        self.tk_image = None       # ImageTk
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        self.tool = "bbox" # 'bbox', 'polygon', 'select'
        self.current_class_id = 0 # Default class
        self.shapes = [] # List of shape dicts: {'type': 'bbox'/'poly', 'points': [], 'id': canvas_id}
        self.selected_shape_index = None # Index in self.shapes
        
        # Temporary drawing state
        self.start_x = None
        self.start_y = None
        self.current_shape_id = None
        self.poly_points = []
        
        self._setup_ui()
        self._bind_events()

    def _setup_ui(self):
        # Toolbar
        toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        tk.Button(toolbar, text="Open Dir", command=self.open_dir).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="Save (s)", command=self.save_labels).pack(side=tk.LEFT, padx=2, pady=2)
        
        tk.Frame(toolbar, width=20).pack(side=tk.LEFT) # Spacer
        
        self.btn_bbox = tk.Button(toolbar, text="Rect Tool (w)", command=lambda: self.set_tool("bbox"), relief=tk.SUNKEN)
        self.btn_bbox.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.btn_poly = tk.Button(toolbar, text="Poly Tool (e)", command=lambda: self.set_tool("polygon"))
        self.btn_poly.pack(side=tk.LEFT, padx=2, pady=2)

        self.btn_select = tk.Button(toolbar, text="Select (q)", command=lambda: self.set_tool("select"))
        self.btn_select.pack(side=tk.LEFT, padx=2, pady=2)
        
        tk.Frame(toolbar, width=20).pack(side=tk.LEFT) # Spacer

        tk.Button(toolbar, text="< Prev (a)", command=self.prev_image).pack(side=tk.LEFT, padx=2, pady=2)
        self.lbl_counter = tk.Label(toolbar, text="0 / 0")
        self.lbl_counter.pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Next > (d)", command=self.next_image).pack(side=tk.LEFT, padx=2, pady=2)

        # Auto-save toggle
        self.autosave_var = tk.BooleanVar(value=True)
        tk.Checkbutton(toolbar, text="Auto-save", variable=self.autosave_var).pack(side=tk.LEFT, padx=10)

        # Main Canvas area
        self.canvas_frame = tk.Frame(self.root)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="gray")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Status Bar
        self.status = tk.Label(self.root, text="Welcome! Open a directory to start.", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_events(self):
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Button-3>", self.on_right_click) # Right click to close poly
        self.canvas.bind("<Motion>", self.on_mouse_move)    # For polygon guide line
        
        self.root.bind("<Key-w>", lambda e: self.set_tool("bbox"))
        self.root.bind("<Key-e>", lambda e: self.set_tool("polygon"))
        self.root.bind("<Key-q>", lambda e: self.set_tool("select"))
        self.root.bind("<Key-d>", lambda e: self.next_image())
        self.root.bind("<Key-a>", lambda e: self.prev_image())
        self.root.bind("<Key-s>", lambda e: self.save_labels())
        self.root.bind("<Key-z>", lambda e: self.undo_last())
        self.root.bind("<Delete>", lambda e: self.delete_selected())
        self.root.bind("<BackSpace>", lambda e: self.delete_selected())

    def set_tool(self, tool):
        self.tool = tool
        self.btn_bbox.config(relief=tk.SUNKEN if tool == "bbox" else tk.RAISED)
        self.btn_poly.config(relief=tk.SUNKEN if tool == "polygon" else tk.RAISED)
        self.btn_select.config(relief=tk.SUNKEN if tool == "select" else tk.RAISED)
        
        if tool == "select":
             self.canvas.config(cursor="arrow")
             self.status.config(text=f"Selected Tool: SELECT (Click to select, Delete/Backspace to remove)")
        elif tool == "bbox":
            self.canvas.config(cursor="crosshair")
            self.status.config(text=f"Selected Tool: BBOX")
        else:
            self.canvas.config(cursor="tcross")
            self.status.config(text=f"Selected Tool: POLYGON")
            
        # Reset poly state if switching
        self.poly_points = []
        if self.current_shape_id:
            self.canvas.delete(self.current_shape_id)
            self.current_shape_id = None
        
        # Clear selection
        self.deselect_all()

    def open_dir(self):
        d = filedialog.askdirectory()
        if not d: return
        self.image_dir = d
        exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp')
        all_files = os.listdir(d)
        print(f"DEBUG: Scanning directory: {d}")
        print(f"DEBUG: Found {len(all_files)} files total.")
        
        self.image_list = sorted([f for f in all_files if f.lower().endswith(exts)])
        print(f"DEBUG: Found {len(self.image_list)} images with extensions {exts}")
        if not self.image_list:
             print("DEBUG: files found:", all_files)

        self.current_idx = 0
        if not self.image_list:
            messagebox.showinfo("Info", f"No images found in directory.\nFound {len(all_files)} files total.\nSee console for details.")
            return
        self.load_image()

    def load_image(self):
        if not self.image_list: return
        
        # Clear existing
        # Clear existing
        self.canvas.delete("all")
        self.shapes = []
        self.selected_shape_index = None # Reset selection
        self.poly_points = []
        
        fname = self.image_list[self.current_idx]
        path = os.path.join(self.image_dir, fname)
        
        image = Image.open(path)
        self.current_image = image
        
        # Resize to fit canvas
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10: # not mapped yet
            cw, ch = 800, 600
            
        iw, ih = image.size
        ratio = min(cw/iw, ch/ih)
        if ratio > 1: ratio = 1 # Don't upscale small images
        
        new_size = (int(iw * ratio), int(ih * ratio))
        self.scale = ratio
        self.tk_image = ImageTk.PhotoImage(image.resize(new_size, Image.Resampling.LANCZOS))
        
        # Center image
        self.offset_x = (cw - new_size[0]) // 2
        self.offset_y = (ch - new_size[1]) // 2
        
        self.canvas.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self.tk_image)
        
        self.lbl_counter.config(text=f"{self.current_idx + 1} / {len(self.image_list)}")
        self.status.config(text=f"Loaded: {fname} | Size: {iw}x{ih}")
        
        # Load existing labels if any
        self.load_existing_labels(fname)

    def next_image(self):
        if self.current_idx < len(self.image_list) - 1:
            if self.autosave_var.get():
                self.save_labels() # Auto-save
            self.current_idx += 1
            self.load_image()

    def prev_image(self):
        if self.current_idx > 0:
            if self.autosave_var.get():
                self.save_labels() # Auto-save
            self.current_idx -= 1
            self.load_image()

    # --- Drawing Logic ---

    def on_mouse_down(self, event):
        if not self.current_image: return
        x, y = event.x, event.y
        
        if self.tool == 'select':
             self.select_shape_at(x, y)
             return

        if self.tool == 'bbox':
            self.start_x = x
            self.start_y = y
            self.current_shape_id = self.canvas.create_rectangle(x, y, x, y, outline='red', width=2)
            
        elif self.tool == 'polygon':
            self.poly_points.append((x, y))
            r = 3
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill='green', outline='green', tags='poly_temp')
            if len(self.poly_points) > 1:
                # connect last two points
                x1, y1 = self.poly_points[-2]
                x2, y2 = self.poly_points[-1]
                self.canvas.create_line(x1, y1, x2, y2, fill='green', width=2, tags='poly_temp')

    def on_mouse_drag(self, event):
        if self.tool == 'bbox' and self.current_shape_id:
            cur_x, cur_y = event.x, event.y
            self.canvas.coords(self.current_shape_id, self.start_x, self.start_y, cur_x, cur_y)

    def on_mouse_up(self, event):
        if self.tool == 'bbox' and self.current_shape_id:
            x1, y1, x2, y2 = self.canvas.coords(self.current_shape_id)
            # Normalize and store
            if abs(x2 - x1) > 5 and abs(y2 - y1) > 5: # Avoid tiny accidental clicks
                self.shapes.append({
                    'type': 'bbox',
                    'points': [(x1, y1), (x2, y2)],
                    'id': self.current_shape_id
                })
                self.current_shape_id = None
            else:
                self.canvas.delete(self.current_shape_id)
                self.current_shape_id = None

    def on_mouse_move(self, event):
        if self.tool == 'polygon' and len(self.poly_points) > 0:
            # Draw rubber band line
            self.canvas.delete('rubber_band')
            last_x, last_y = self.poly_points[-1]
            self.canvas.create_line(last_x, last_y, event.x, event.y, fill='lightgreen', dash=(4,4), tags='rubber_band')

    def on_right_click(self, event):
        if self.tool == 'polygon' and len(self.poly_points) > 2:
            # Close polygon
            self.canvas.delete('poly_temp')
            self.canvas.delete('rubber_band')
            
            # Create final polygon
            # Flatten points for create_polygon
            flat_points = [coord for point in self.poly_points for coord in point]
            poly_id = self.canvas.create_polygon(flat_points, outline='green', fill='', width=2)
            
            self.shapes.append({
                'type': 'poly',
                'points': self.poly_points,
                'id': poly_id
            })
            self.poly_points = []
            
    # --- Selection Logic ---

    def select_shape_at(self, x, y):
        self.deselect_all()
        # Iterate backwards to select top-most
        for i in range(len(self.shapes) - 1, -1, -1):
            shape = self.shapes[i]
            sid = shape['id']
            # Simple bounding box hit test for now (works for poly too roughly, better to use proper overlap)
            coords = self.canvas.bbox(sid)
            if not coords: continue
            if coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                self.selected_shape_index = i
                # Highlight
                self.canvas.itemconfig(sid, width=4, outline='magenta')
                if shape['type'] == 'poly':
                     self.canvas.itemconfig(sid, fill='green', stipple='gray50') # Slight fill
                self.status.config(text=f"Selected Shape {i}. Press Delete to remove.")
                return

    def deselect_all(self):
        if self.selected_shape_index is not None:
             # Restore visuals
             shape = self.shapes[self.selected_shape_index]
             sid = shape['id']
             color = 'red' if shape['type'] == 'bbox' else 'green'
             self.canvas.itemconfig(sid, width=2, outline=color)
             if shape['type'] == 'poly':
                 self.canvas.itemconfig(sid, fill='')
        self.selected_shape_index = None

    def delete_selected(self):
        if self.selected_shape_index is not None:
            shape = self.shapes.pop(self.selected_shape_index)
            self.canvas.delete(shape['id'])
            self.selected_shape_index = None
            self.status.config(text="Shape deleted.")
            self.save_labels() # Auto-save if enabled

    def undo_last(self):
        if self.shapes:
            last = self.shapes.pop()
            self.canvas.delete(last['id'])
        elif self.poly_points: # Undo last point of poly being drawn
             self.poly_points.pop()
             self.canvas.delete('poly_temp')
             # Redraw partial poly
             for i, (x, y) in enumerate(self.poly_points):
                 r = 3
                 self.canvas.create_oval(x-r, y-r, x+r, y+r, fill='green', outline='green', tags='poly_temp')
                 if i > 0:
                     px, py = self.poly_points[i-1]
                     self.canvas.create_line(px, py, x, y, fill='green', width=2, tags='poly_temp')

    # --- Saving / Loading ---

    def canvas_to_img_coords(self, x, y):
        # Remove offset and unscale
        ix = (x - self.offset_x) / self.scale
        iy = (y - self.offset_y) / self.scale
        # Clamp
        w, h = self.current_image.size
        ix = max(0, min(w, ix))
        iy = max(0, min(h, iy))
        return ix, iy

    def save_labels(self):
        if not self.current_image: return
        fname = self.image_list[self.current_idx]
        txt_name = os.path.splitext(fname)[0] + ".txt"
        path = os.path.join(self.image_dir, txt_name)
        
        w, h = self.current_image.size
        
        lines = []
        for shape in self.shapes:
            if shape['type'] == 'bbox':
                p1, p2 = shape['points']
                x1, y1 = self.canvas_to_img_coords(*p1)
                x2, y2 = self.canvas_to_img_coords(*p2)
                
                # Normalize xyxy to xywh center
                min_x, max_x = sorted([x1, x2])
                min_y, max_y = sorted([y1, y2])
                
                bw = max_x - min_x
                bh = max_y - min_y
                cx = min_x + bw/2
                cy = min_y + bh/2
                
                # Normalize 0-1
                lines.append(f"{self.current_class_id} {cx/w:.6f} {cy/h:.6f} {bw/w:.6f} {bh/h:.6f}")
                
            elif shape['type'] == 'poly':
                pts = []
                for px, py in shape['points']:
                    ix, iy = self.canvas_to_img_coords(px, py)
                    pts.append(f"{ix/w:.6f} {iy/h:.6f}")
                lines.append(f"{self.current_class_id} {' '.join(pts)}")

        with open(path, 'w') as f:
            f.write('\n'.join(lines))
        
        print(f"Saved {path} ({'Empty' if not lines else 'Labels'})")
        self.status.config(text=f"Saved {'(Empty) ' if not lines else ''}labels for {fname}")

    def load_existing_labels(self, fname):
        txt_name = os.path.splitext(fname)[0] + ".txt"
        path = os.path.join(self.image_dir, txt_name)
        if not os.path.exists(path): return

        w, h = self.current_image.size
        
        with open(path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if not parts: continue
                cls = parts[0]
                coords = [float(x) for x in parts[1:]]
                
                if len(coords) == 4: # BBox
                    cx, cy, bw, bh = coords
                    # Denormalize
                    cx *= w
                    cy *= h
                    bw *= w
                    bh *= h
                    
                    x1 = cx - bw/2
                    y1 = cy - bh/2
                    x2 = cx + bw/2
                    y2 = cy + bh/2
                    
                    # To canvas
                    cx1 = x1 * self.scale + self.offset_x
                    cy1 = y1 * self.scale + self.offset_y
                    cx2 = x2 * self.scale + self.offset_x
                    cy2 = y2 * self.scale + self.offset_y
                    
                    sid = self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline='red', width=2)
                    self.shapes.append({
                        'type': 'bbox', 
                        'points': [(cx1, cy1), (cx2, cy2)], 
                        'id': sid
                    })
                    
                elif len(coords) > 4: # Polygon
                    poly_pts = []
                    flat_pts = []
                    for i in range(0, len(coords), 2):
                        ix = coords[i] * w
                        iy = coords[i+1] * h
                        
                        cx = ix * self.scale + self.offset_x
                        cy = iy * self.scale + self.offset_y
                        poly_pts.append((cx, cy))
                        flat_pts.extend([cx, cy])
                    
                    sid = self.canvas.create_polygon(flat_pts, outline='green', fill='', width=2)
                    self.shapes.append({
                        'type': 'poly',
                        'points': poly_pts,
                        'id': sid
                    })

if __name__ == "__main__":
    root = tk.Tk()
    app = PotholeLabeler(root)
    root.mainloop()
