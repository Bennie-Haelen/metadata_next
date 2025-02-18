import json
import tkinter as tk
from tkinter import ttk, filedialog

class SchemaViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FHIR Schema Viewer")
        self.root.geometry("900x600")

        # Button to select JSON file
        self.file_button = ttk.Button(root, text="Select JSON File", command=self.load_json_file)
        self.file_button.pack(pady=10)

        # Split UI into two sections
        self.frame_left = ttk.Frame(root, width=350)
        self.frame_left.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        self.frame_right = ttk.Frame(root)
        self.frame_right.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=10, pady=10)

        # TreeView Widget (Left Panel)
        self.tree = ttk.Treeview(self.frame_left)
        self.tree.pack(expand=True, fill=tk.BOTH)

        # Schema Details (Right Panel)
        self.details_label = ttk.Label(self.frame_right, text="Select a field to view details", font=("Arial", 12))
        self.details_label.pack(anchor="w", pady=10)

        self.name_label = ttk.Label(self.frame_right, text="", font=("Arial", 10, "bold"))
        self.name_label.pack(anchor="w")

        self.type_label = ttk.Label(self.frame_right, text="", font=("Arial", 10))
        self.type_label.pack(anchor="w")

        self.description_label = ttk.Label(self.frame_right, text="", wraplength=450, justify="left")
        self.description_label.pack(anchor="w", pady=5)

        self.hipaa_label = ttk.Label(self.frame_right, text="", font=("Arial", 10))
        self.hipaa_label.pack(anchor="w")

        self.phi_pii_label = ttk.Label(self.frame_right, text="", font=("Arial", 10))
        self.phi_pii_label.pack(anchor="w")

        self.description_length_label = ttk.Label(self.frame_right, text="", font=("Arial", 10, "italic"))
        self.description_length_label.pack(anchor="w", pady=5)

        # Bind selection event
        self.tree.bind("<<TreeviewSelect>>", self.display_details)

    def load_json_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if file_path:
            with open(file_path, "r") as file:
                schema_data = json.load(file)
            self.populate_tree(schema_data)

    def populate_tree(self, schema, parent=""):
        """ Recursively populates the tree with schema fields. """
        self.tree.delete(*self.tree.get_children())  # Clear existing tree if starting fresh

        def insert_nodes(fields, parent_node):
            for field in fields:
                values = (
                    field.get("type", ""),
                    field.get("description", ""),
                    field.get("HIPAA", False),
                    field.get("PHI/PII", False)
                )
                node_id = self.tree.insert(parent_node, "end", text=field["name"], values=values)
                if "fields" in field and isinstance(field["fields"], list):  # Ensure fields exist and are a list
                    insert_nodes(field["fields"], node_id)

        insert_nodes(schema, parent)

    def display_details(self, event):
        selected_item = self.tree.selection()
        if selected_item:
            node_id = selected_item[0]
            field_name = self.tree.item(node_id, "text")
            field_type = self.tree.item(node_id, "values")[0]
            field_description = self.tree.item(node_id, "values")[1]
            field_hipaa = self.tree.item(node_id, "values")[2]
            field_phi_pii = self.tree.item(node_id, "values")[3]

            self.name_label.config(text=f"Field Name: {field_name}")
            self.type_label.config(text=f"Type: {field_type}")
            self.description_label.config(text=f"Description: {field_description}")
            self.hipaa_label.config(text=f"HIPAA: {'Yes' if field_hipaa else 'No'}")
            self.phi_pii_label.config(text=f"PHI/PII: {'Yes' if field_phi_pii else 'No'}")
            self.description_length_label.config(text=f"Description Length: {len(field_description)} characters")

# Run Application
if __name__ == "__main__":
    root = tk.Tk()
    app = SchemaViewerApp(root)
    root.mainloop()
