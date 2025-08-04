"""
mistral_form_filler.py

This module handles the automated filling of PDF forms with both text and images
for real estate appraisal reports. It supports:

1. Mapping extracted text fields (from OCR and AI) into the correct PDF field locations.
2. Inserting JPEG images into designated placeholder fields on the form.
3. Updating dropdowns, checkboxes, and text fields based on type detection.
4. Saving the final output PDF after inserting all data.

Key Components:
---------------
- FIELD_MAPPING: Dict mapping PDF field names to logical data keys.
- IMAGE_FIELD_MAP: Dict mapping PDF image field names to expected image keys.
- fill_pdf_with_text_and_images(): Fills the form with both text and images.
- fill_pdf_fields(): Text-only legacy filling function (preserved for compatibility).
- debug_pdf_fields(): Helper function to list all field names and locations.
- test_combined_filling(): Manual test runner to verify combined filling works.

Dependencies:
-------------
- PyMuPDF (`fitz`) for PDF manipulation
- `os` and `logging` for diagnostics and file access

Usage:
------
This module is invoked by the Streamlit app after extracting values via OCR and AI.
"""

import fitz  # PyMuPDF
import logging
import os

logging.basicConfig(level=logging.INFO)

# Text field mappings
FIELD_MAPPING = {
    # Property Info
    "1_1_6": "property_address",
    "=0_2_2": "property_address",
    "=0_1_40": "legal_description",
    "1_1_278": "source",
    "1_1_47": "municipality",
    "1_1_563": "property_id",

    # Assessment Info
    "1_1_50": "assessment_value",
    "1_1_51": "assessment_date",
    "1_1_52": "property_taxes",
    "1_1_53": "tax_year",

    # Site & Zoning
    "=0_2_117": "site_dimensions",
    "=0_2_17": "lot_size",
    "1_1_328": "lot_size_units",
    "=0_2_231": "zoning",
    "=0_2_225": "year_built",

    # MLS Data
    "=0_2_61": "mls_source",
    "=0_2_43": "date_of_sale",
    "=0_2_44": "sale_price",
    "=0_2_62": "days_on_market",
    "=0_2_18": "property_type",
    "=0_2_19": "design",
    "=0_2_16": "living_floor_area",
    "=0_2_114": "room_counts",
    "=0_2_115": "bedrooms",
    "=0_2_116": "number_of_bathrooms",
    "=0_2_20": "basement_info",
}

# Image field mapping
IMAGE_FIELD_MAP = {
    "65_1_13": "comparable_photo_1",
    "65_1_17": "comparable_photo_2", 
    "65_1_21": "comparable_photo_3",
    "61_1_10": "location_map",
    "57_1_10": "plot_map",
}

def fill_pdf_with_text_and_images(input_pdf_path: str, output_pdf_path: str, 
                                 field_data: dict, image_dict: dict) -> bool:
    """
    Fill both text fields and image fields in the given PDF and save the result.

    Args:
        input_pdf_path (str): Path to the input PDF form.
        output_pdf_path (str): Path where the filled PDF will be saved.
        field_data (dict): Dictionary mapping field names to text values.
        image_dict (dict): Dictionary mapping image keys to image file paths.

    Returns:
        bool: True if at least one text field or image was filled, False otherwise.
    """
    try:
        doc = fitz.open(input_pdf_path)
        text_filled = 0
        images_inserted = 0
        
        print("=== COMBINED FILLING: TEXT + IMAGES ===")
        print(f"Input PDF: {input_pdf_path}")
        print(f"Text fields to fill: {len([k for k, v in field_data.items() if v])}")
        print(f"Images to insert: {len(image_dict)}")
        
        # Process each page
        for page_num in range(doc.page_count):
            page = doc[page_num]
            widgets = list(page.widgets())  # Convert to list to avoid generator issues
            
            print(f"\nPage {page_num + 1}: {len(widgets)} widgets")
            
            for widget in widgets:
                field_name = widget.field_name
                if not field_name:
                    continue
                
                # 1. CHECK IF IT'S A TEXT FIELD
                data_key = FIELD_MAPPING.get(field_name)
                if data_key and data_key in field_data:
                    value = field_data[data_key]
                    if value is not None and value != "":
                        try:
                            if widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                                checked = str(value).lower() in ["yes", "true", "on", "1"]
                                widget.field_value = "Yes" if checked else "Off"
                            elif widget.field_type == fitz.PDF_WIDGET_TYPE_COMBOBOX:
                                widget.field_value = str(value).strip()
                            else:
                                clean_value = str(value).strip()
                                clean_value = clean_value.replace('$', '').replace('\\times', '×')
                                if data_key == "assessment_value" and not clean_value.startswith("$"):
                                    clean_value = f"${clean_value}"
                                widget.field_value = clean_value
                            
                            widget.update()  # Update needed for text fields
                            text_filled += 1
                            print(f"  ✅ Text: {field_name} = '{value}'")
                            
                        except Exception as e:
                            print(f"  ❌ Text fill error for {field_name}: {e}")
                
                # 2. CHECK IF IT'S AN IMAGE FIELD
                image_key = IMAGE_FIELD_MAP.get(field_name)
                if image_key and image_key in image_dict:
                    image_path = image_dict[image_key]
                    if os.path.exists(image_path):
                        try:
                            rect = widget.rect
                            print(f"  🖼️ Inserting {image_key} into {field_name} at {rect}")
                            
                            # Use the exact same method as your working test script
                            page.insert_image(rect, filename=image_path)
                            images_inserted += 1
                            print(f"  ✅ Image: {field_name} = {image_key}")
                            
                        except Exception as e:
                            print(f"  ❌ Image insert error for {field_name}: {e}")
                    else:
                        print(f"  ❌ Image file not found: {image_path}")
        
        # SAVE ONCE after both text and images are processed
        doc.save(output_pdf_path)
        doc.close()
        
        print(f"\n✅ FINAL SUMMARY:")
        print(f"   Text fields filled: {text_filled}")
        print(f"   Images inserted: {images_inserted}")
        print(f"   Output saved: {output_pdf_path}")
        
        return (text_filled > 0 or images_inserted > 0)
        
    except Exception as e:
        print(f"❌ Combined filling error: {e}")
        import traceback
        traceback.print_exc()
        return False

# Keep your original functions for backward compatibility
def fill_pdf_fields(input_pdf_path: str, output_pdf_path: str, data_dict: dict) -> bool:
    """
    Fill only text fields in a PDF form using the provided data dictionary.

    Args:
        input_pdf_path (str): Path to the input PDF file.
        output_pdf_path (str): Path to the output PDF file with filled text fields.
        data_dict (dict): Dictionary mapping field names to values.

    Returns:
        bool: True if at least one text field was filled, False otherwise.
    """
    try:
        doc = fitz.open(input_pdf_path)
        filled_count = 0
        
        logging.info("=== FILLING PDF FIELDS WITH TEXT ONLY ===")
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            widgets = page.widgets()
            
            for widget in widgets:
                field_name = widget.field_name
                
                if field_name:
                    data_key = FIELD_MAPPING.get(field_name)
                    
                    if data_key is None:
                        continue
                    if data_key not in data_dict:
                        continue
                    
                    value = data_dict[data_key]
                    if value is None or value == "":
                        continue
                    
                    try:
                        if widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                            checked = str(value).lower() in ["yes", "true", "on", "1"]
                            widget.field_value = "Yes" if checked else "Off"
                        elif widget.field_type == fitz.PDF_WIDGET_TYPE_COMBOBOX:
                            combo_value = str(value).strip()
                            widget.field_value = combo_value
                            widget.update()
                            logging.info(f"✅ Filled combo box '{field_name}' with '{combo_value}'")
                        else:
                            clean_value = str(value).strip()
                            clean_value = clean_value.replace('$', '').replace('\\times', '×')
                            if data_key == "assessment_value" and not clean_value.startswith("$"):
                                clean_value = f"${clean_value}"
                            widget.field_value = clean_value

                        widget.update()
                        filled_count += 1
                        logging.info(f"✅ Filled field: {field_name} -> {data_key}: '{value}'")
                        
                    except Exception as e:
                        logging.error(f"❌ Failed to fill field '{field_name}': {e}")
        
        doc.save(output_pdf_path)
        doc.close()
        
        logging.info(f"\n✅ Total fields filled: {filled_count}")
        logging.info(f"📁 Output saved to: {output_pdf_path}")
        return filled_count > 0
        
    except Exception as e:
        logging.error(f"❌ Failed to fill PDF: {e}")
        return False

# Debug function
def debug_pdf_fields(pdf_path: str):
    """
    Print all interactive field names, types, and coordinates in the given PDF.

    Args:
        pdf_path (str): Path to the PDF file to inspect.

    Returns:
        None
    """
    try:
        doc = fitz.open(pdf_path)
        print("\n=== ALL PDF FIELDS ===")
        
        for page_num, page in enumerate(doc):
            widgets = list(page.widgets())
            if widgets:
                print(f"\nPage {page_num + 1}:")
                for widget in widgets:
                    field_name = widget.field_name
                    field_type = widget.field_type
                    rect = widget.rect
                    print(f"  Field: '{field_name}' | Type: {field_type} | Rect: {rect}")
        
        doc.close()
    except Exception as e:
        print(f"Error debugging PDF: {e}")

# Test function
# def test_combined_filling():
#     """Test the combined filling function"""
#     test_text_data = {
#         "property_address": "123 Test Street",
#         "legal_description": "Test Legal Description",
#         "zoning": "R1",
#         "property_id": "12345",
#         "bedrooms": "3",
#         "bathrooms": "2",
#         "lot_size": "50x100"
#     }
    
#     test_image_data = {
#         "comparable_photo_1": "cat.jpg"  # Replace with actual image path
#     }
    
#     success = fill_pdf_with_text_and_images(
#         "0324Template-freehold(2).pdf", 
#         "test_combined_output.pdf", 
#         test_text_data, 
#         test_image_data
#     )
#     print(f"Combined test result: {'SUCCESS' if success else 'FAILED'}")

# if __name__ == "__main__":
#     test_combined_filling()