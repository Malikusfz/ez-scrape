import streamlit as st
import pandas as pd
from core.dashboard import get_project_level_stats, get_subproject_level_stats
from core.token_estimator import TokenEstimator
import os

def dashboard_tab(output_root):
    """
    Streamlit tab for the project dashboard.
    """
    st.header("Dashboard")

    # Project-Level Statistics
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Project-Level Summary")
    with col2:
        if st.button("Recalculate All Tokens", key="recalculate_tokens_button"):
            try:
                # Count total number of projects and subprojects
                total_items = sum(
                    sum(1 for subproject in os.listdir(os.path.join(output_root, project))
                        if os.path.isdir(os.path.join(output_root, project, subproject)))
                    for project in os.listdir(output_root)
                    if os.path.isdir(os.path.join(output_root, project))
                )
                
                if total_items == 0:
                    st.warning("No projects or subprojects found.")
                    return
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                current_item = 0
                
                for project in os.listdir(output_root):
                    project_path = os.path.join(output_root, project)
                    if os.path.isdir(project_path):
                        for subproject in os.listdir(project_path):
                            subproject_path = os.path.join(project_path, subproject)
                            if os.path.isdir(subproject_path):
                                status_text.text(f"Processing {project}/{subproject}...")
                                estimator = TokenEstimator(subproject_path)
                                
                                # Process PDFs if they exist
                                pdf_folder = os.path.join(subproject_path, "pdfs", "scraped-pdfs")
                                if os.path.exists(pdf_folder) and any(f.endswith(".pdf") for f in os.listdir(pdf_folder)):
                                    estimator.process_pdfs(pdf_folder)
                                
                                # Process WARCs if they exist
                                warc_folder = os.path.join(subproject_path, "warcs", "scraped-warcs")
                                if os.path.exists(warc_folder) and any(f.endswith(".warc") for f in os.listdir(warc_folder)):
                                    estimator.process_warcs(warc_folder)
                                
                                current_item += 1
                                progress_bar.progress(current_item / total_items)
                
                status_text.text("Token recalculation completed!")
                progress_bar.progress(1.0)
                st.success("Token recalculation completed for all projects!")
                st.rerun()
            except Exception as e:
                st.error(f"Token recalculation failed: {e}")

    project_data = get_project_level_stats(output_root)
    if project_data:
        project_df = pd.DataFrame(
            project_data,
            columns=["Project", "Files Count", "Token Count", "Compressed Files Size", "Bytes Count"]
        )
        st.dataframe(project_df, use_container_width=True)
    else:
        st.warning("No project-level data available.")

    # Subproject-Level Statistics
    st.subheader("Subproject-Level Details")
    subproject_data = get_subproject_level_stats(output_root)
    if subproject_data:
        subproject_df = pd.DataFrame(
            subproject_data,
            columns=["Project", "Subproject", "Files Count", "Token Count", "Bytes Count"]
        )
        st.dataframe(subproject_df, use_container_width=True)
    else:
        st.warning("No subproject-level data available.")

    # Copy Compressed Files Section
    st.subheader("Copy Compressed Files")
    st.write("Copy compressed files (zip and warc.gz) from subprojects to their parent projects.")

    # Project selection
    projects = [d for d in os.listdir(output_root) if os.path.isdir(os.path.join(output_root, d))]
    if not projects:
        st.warning("No projects found.")
    else:
        selected_project = st.selectbox("Select Project", projects, key="copy_files_project")
        project_path = os.path.join(output_root, selected_project)
    
        # Define file types to copy
        file_types = ["zip", "warc.gz"]
    
        if st.button("Copy Files"):
            try:
                files_copied = 0
                with st.spinner("Copying files..."):
                    # Get all subprojects
                    subprojects = [d for d in os.listdir(project_path) if os.path.isdir(os.path.join(project_path, d))]
                    
                    # Create progress bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Create compressed_files directory in project root
                    project_compressed_dir = os.path.join(project_path, "compressed_files")
                    os.makedirs(project_compressed_dir, exist_ok=True)
                    
                    for idx, subproject in enumerate(subprojects):
                        subproject_path = os.path.join(project_path, subproject)
                        
                        # Check compressed directory
                        compressed_dir = os.path.join(subproject_path, "compressed")
                        
                        if os.path.exists(compressed_dir):
                            # Copy files based on selected types
                            for file in os.listdir(compressed_dir):
                                if any(file.endswith(ext) for ext in file_types):
                                    source = os.path.join(compressed_dir, file)
                                    destination = os.path.join(project_compressed_dir, file)
                                    
                                    # Copy file if it doesn't exist or is newer
                                    if not os.path.exists(destination) or \
                                       os.path.getmtime(source) > os.path.getmtime(destination):
                                        import shutil
                                        shutil.copy2(source, destination)
                                        files_copied += 1
                                        
                                    status_text.text(f"Processing: {subproject} - {file}")
                        
                        # Update progress
                        progress_bar.progress((idx + 1) / len(subprojects))
                    
                    if files_copied > 0:
                        st.success(f"Successfully copied {files_copied} files to {project_compressed_dir}")
                    else:
                        st.info("No new files to copy.")
                    
                    # Clear progress indicators
                    progress_bar.empty()
                    status_text.empty()
                    
            except Exception as e:
                st.error(f"Error copying files: {e}")
