"""
Streamlit App: PDF Form Filler for Appraisal Reports

This app allows users to:
1. Upload an MLS listing and an Assessment PDF.
2. Optionally upload up to 5 JPEG images (e.g., property photos, maps).
3. Automatically extract relevant data using Mistral OCR API.
4. Fill a PDF template with the extracted text and image data.
5. View a summary and download the filled-in PDF.
"""

import streamlit as st
import hashlib
import tempfile
from dotenv import load_dotenv
import os
import traceback
from extractor import extract_from_mls_direct, extract_from_assessment_direct
from filler import fill_pdf_with_text_and_images 

load_dotenv() 

st.title("PDF Form Filler for Appraisal Reports")

# Configuration section
st.sidebar.header("Configuration")
template_file = st.sidebar.text_input("Template PDF filename", "0324Template-freehold(2).pdf")
appraiser_name = st.sidebar.text_input("Appraiser Name", "John Doe, P.App")

# Mistral API key
api_key = os.getenv("TAVILY_API_KEY")

if not api_key:
    st.error("API key not found. Please set the TAVILY_API_KEY environment variable.")
    st.stop()

# File upload section
st.header("Upload Documents")
mls_pdf = st.file_uploader("Upload MLS Listing PDF", type="pdf", key="mls_upload")
assessment_pdf = st.file_uploader("Upload Assessment PDF", type="pdf", key="assessment_upload")

# Image upload section
st.header("Optional Images (JPEG)")
comp1 = st.file_uploader("Comparable Photo #1", type=["jpg", "jpeg"], key="comp1")
comp2 = st.file_uploader("Comparable Photo #2", type=["jpg", "jpeg"], key="comp2")
comp3 = st.file_uploader("Comparable Photo #3", type=["jpg", "jpeg"], key="comp3")
location_map = st.file_uploader("Location Map", type=["jpg", "jpeg"], key="location_map")
plot_map = st.file_uploader("Plot Map", type=["jpg", "jpeg"], key="plot_map")

if mls_pdf and assessment_pdf:
    st.markdown("✅ PDFs uploaded. Now upload optional images (if any), then click below.")

    if st.button("🚀 Generate Filled PDF"):
        try:
            # Create file hashes for caching
            mls_content = mls_pdf.read()
            assessment_content = assessment_pdf.read()
            mls_hash = hashlib.md5(mls_content).hexdigest()
            assessment_hash = hashlib.md5(assessment_content).hexdigest()

            # Include image names in cache key
            image_keys = "".join([
                f"{comp1.name if comp1 else ''}{comp2.name if comp2 else ''}{comp3.name if comp3 else ''}"
                f"{location_map.name if location_map else ''}{plot_map.name if plot_map else ''}"
            ])
            cache_key = f"{mls_hash}_{assessment_hash}_{hashlib.md5(image_keys.encode()).hexdigest()}"

            if 'extraction_cache' not in st.session_state:
                st.session_state.extraction_cache = {}
            if 'pdf_generated' not in st.session_state:
                st.session_state.pdf_generated = {}

            # Check if extraction is cached
            if cache_key in st.session_state.extraction_cache:
                st.success("📋 Using cached extraction results (no re-processing needed)")
                mls_data, assessment_data = st.session_state.extraction_cache[cache_key]
            else:
                st.info("🔄 Processing uploaded files for the first time...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as mls_temp:
                    mls_temp.write(mls_content)
                    mls_path = mls_temp.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as assess_temp:
                    assess_temp.write(assessment_content)
                    assess_path = assess_temp.name

                with st.spinner("🤖 Extracting MLS data..."):
                    mls_data = extract_from_mls_direct(mls_path, api_key, True)
                with st.spinner("🤖 Extracting Assessment data..."):
                    assessment_data = extract_from_assessment_direct(assess_path, api_key, True)

                st.session_state.extraction_cache[cache_key] = (mls_data, assessment_data)
                st.success("✅ Extraction completed and cached!")

                try:
                    os.unlink(mls_path)
                    os.unlink(assess_path)
                except:
                    pass

            # Merge extracted data
            field_values = {**mls_data, **assessment_data}
            if appraiser_name:
                field_values["appraiser_name"] = appraiser_name
            if "property_address" in field_values:
                field_values["subject_address"] = field_values["property_address"]

            if not os.path.exists(template_file):
                st.error(f"Template file '{template_file}' not found.")
            else:
                # Generate output path
                output_filename = f"filled_appraisal_form_{cache_key[:8]}.pdf"
                final_output = os.path.join(tempfile.gettempdir(), output_filename)
                
                # Check if already generated (CACHED)
                if cache_key in st.session_state.pdf_generated:
                    final_output = st.session_state.pdf_generated[cache_key]
                    st.success("📋 Using cached PDF (no re-processing needed)")
                    
                    # Show cached summary
                    filled_count = len([v for v in field_values.values() if v])
                    image_count = len([f for f in [comp1, comp2, comp3, location_map, plot_map] if f])
                    st.info(f"📊 Cached PDF has {filled_count} text fields and {image_count} images")
                
                else:
                    # First time generation - do the work
                    st.info("🔄 Generating PDF for the first time...")
                    
                    # Build image_dict with proper file handling
                    image_dict = {}
                    temp_images = []
                    
                    with st.spinner("📄 Preparing images..."):
                        for key, file_obj in [
                            ("comparable_photo_1", comp1),
                            ("comparable_photo_2", comp2),
                            ("comparable_photo_3", comp3),
                            ("location_map", location_map),
                            ("plot_map", plot_map)
                        ]:
                            if file_obj:
                                # Reset file pointer and read content
                                file_obj.seek(0)
                                file_content = file_obj.read()
                                
                                # Create temp file with proper flushing
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
                                    tmp_img.write(file_content)
                                    tmp_img.flush()
                                    os.fsync(tmp_img.fileno())  # Force write to disk
                                    temp_images.append(tmp_img.name)
                                    image_dict[key] = tmp_img.name
                                    
                                st.info(f"✅ Prepared {key}: {len(file_content)} bytes")
                    
                    # Debug temp files
                    if image_dict:
                        st.info("🔍 Verifying temp files...")
                        for key, path in image_dict.items():
                            if os.path.exists(path):
                                size = os.path.getsize(path)
                                st.write(f"  ✅ {key}: {size} bytes")
                            else:
                                st.write(f"  ❌ {key}: Missing!")
                    
                    # COMBINED FILLING: Text + Images in one operation
                    with st.spinner("🎨 Filling PDF with text and images..."):
                        success = fill_pdf_with_text_and_images(
                            template_file,
                            final_output, 
                            field_values,
                            image_dict
                        )
                    
                    if success:
                        # Cache the generated PDF path
                        st.session_state.pdf_generated[cache_key] = final_output
                        st.success("🎉 PDF form filled successfully with text and images!")
                        
                        # Show summary
                        filled_count = len([v for v in field_values.values() if v])
                        image_count = len(image_dict)
                        st.info(f"📊 Filled {filled_count} text fields and inserted {image_count} images")
                        
                    else:
                        st.error("Failed to fill PDF form.")
                        st.stop()
                        
                    # Cleanup temp image files (but keep the final PDF)
                    for temp_path in temp_images:
                        try:
                            os.unlink(temp_path)
                        except:
                            pass

                # Preview extracted data
                with st.expander("Summary of Filled Fields"):
                    filled_count = len([v for v in field_values.values() if v])
                    st.write(f"**Total text fields filled:** {filled_count}")
                    if image_dict:
                        st.write(f"**Images inserted:** {len(image_dict)}")
                        for key in image_dict.keys():
                            st.write(f"  • {key}")
                    
                    st.write("**Text Field Values:**")
                    for key, value in field_values.items():
                        if value:
                            st.write(f"**{key}:** {value}")

                # Download button
                if os.path.exists(final_output):
                    with open(final_output, "rb") as f:
                        st.download_button(
                            label="📄 Download Filled PDF",
                            data=f.read(),
                            file_name="filled_appraisal_form.pdf",
                            mime="application/pdf",
                            key=f"download_btn_{cache_key}",
                            help="Download the PDF with both text fields and images filled"
                        )
                        
                    # Show file info
                    file_size = os.path.getsize(final_output)
                    st.info(f"📁 Generated PDF: {file_size:,} bytes")
                        
                else:
                    st.error("PDF file not found. Please try regenerating.")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            with st.expander("Technical Details"):
                st.code(traceback.format_exc())

else:
    st.info("Please upload both MLS and Assessment PDF files to begin.")

    with st.expander("Instructions"):
        st.markdown("""
        ### How to use this tool:
        1. Upload **MLS PDF** and **Assessment PDF**
        2. (Optional) Upload up to **5 JPEG images**
        3. Configure appraiser name in sidebar
        4. Click "Generate Filled PDF"
        5. Download the completed form
        
        ### ✨ **New Features:**
        - **🎨 Combined Processing** - Text and images filled together
        - **🚀 Smart Caching** - No re-extraction on download clicks
        - **🔍 File Verification** - Ensures images are properly prepared
        - **📊 Detailed Summary** - Shows exactly what was filled
        """)

# Sidebar cache management
st.sidebar.markdown("---")
st.sidebar.subheader("Cache Management")
if st.sidebar.button("🗑️ Clear All Cache"):
    st.session_state.clear()
    st.sidebar.success("Cache cleared!")
    st.rerun()

if 'extraction_cache' in st.session_state:
    cache_count = len(st.session_state.extraction_cache)
    st.sidebar.info(f"📊 Cached extractions: {cache_count}")

if 'pdf_generated' in st.session_state:
    pdf_count = len(st.session_state.pdf_generated)
    st.sidebar.info(f"📄 Generated PDFs: {pdf_count}")