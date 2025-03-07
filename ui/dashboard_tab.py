import streamlit as st
import pandas as pd
import os
import shutil
import time
from datetime import datetime
from core.dashboard import get_project_level_stats, get_subproject_level_stats
from core.token_estimator import TokenEstimator

def dashboard_tab(output_root):
    """
    Streamlit tab for the project dashboard.
    """
    st.header("Dashboard")
    
    # Project-Level Statistics
    st.subheader("Project-Level Summary")
    with st.spinner("Loading project statistics..."):
        project_data = get_project_level_stats(output_root)
    
    if project_data:
        project_df = pd.DataFrame(
            project_data,
            columns=[
                "Project", "Files Count", "Token Count",
                "Compressed Size", "Bytes Count", "WARC Files", "PDF Files", "Last Modified"
            ]
        )
        # Convert timestamps to readable format
        project_df["Last Modified"] = pd.to_datetime(project_df["Last Modified"], unit='s')
        # Sort by newest first
        project_df = project_df.sort_values("Last Modified", ascending=False)
        
        # Reset index to fix row numbering
        project_df = project_df.reset_index(drop=True)
        
        # Format Last Modified column before displaying
        project_df["Last Modified"] = project_df["Last Modified"].dt.strftime("%Y-%m-%d %H:%M")
        
        st.dataframe(project_df, use_container_width=True)
        
        # Add some metrics for quick overview
        total_projects = len(project_data)
        total_files = sum(row[1] for row in project_data)
        total_tokens = sum(row[2] for row in project_data)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Projects", total_projects)
        col2.metric("Total Files", total_files)
        col3.metric("Total Tokens (millions)", f"{total_tokens/1_000_000:.2f}M")
    else:
        st.warning("No project-level data available.")

    # Subproject-Level Statistics
    st.subheader("Subproject-Level Details")
    with st.spinner("Loading subproject statistics..."):
        subproject_data = get_subproject_level_stats(output_root)
    
    if subproject_data:
        subproject_df = pd.DataFrame(
            subproject_data,
            columns=["Project", "Subproject", "Files Count", "Token Count", "Bytes Count", "Last Modified"]
        )
        # Convert timestamps to readable format
        subproject_df["Last Modified"] = pd.to_datetime(subproject_df["Last Modified"], unit='s')
        # Sort by newest first
        subproject_df = subproject_df.sort_values("Last Modified", ascending=False)
        
        # Reset index to fix row numbering
        subproject_df = subproject_df.reset_index(drop=True)
        
        # Format Last Modified column before displaying
        subproject_df["Last Modified"] = subproject_df["Last Modified"].dt.strftime("%Y-%m-%d %H:%M")
        
        st.dataframe(subproject_df, use_container_width=True)
    else:
        st.warning("No subproject-level data available.")
    
    # Dashboard Actions in tabs
    st.subheader("Dashboard Actions")
    tab1, tab2 = st.tabs(["Token Recalculation", "Compression Management"])
    
    with tab1:
        st.subheader("Recalculate All Tokens")
        st.info("This operation will recalculate token counts for all projects and might take a while.")
        if st.button("Recalculate All Tokens", key="recalc_tokens"):
            confirm = st.checkbox("Confirm recalculation of all tokens?")
            if confirm:
                try:
                    # Count total items for progress tracking
                    with st.spinner("Preparing token recalculation..."):
                        projects = [p for p in os.listdir(output_root) if os.path.isdir(os.path.join(output_root, p))]
                        total_items = 0
                        processing_items = []
                        
                        for project in projects:
                            project_path = os.path.join(output_root, project)
                            subprojects = [sp for sp in os.listdir(project_path) 
                                           if os.path.isdir(os.path.join(project_path, sp)) 
                                           and not "compressed" in sp.lower()]
                            for subproject in subprojects:
                                subproject_path = os.path.join(project_path, subproject)
                                # Only count if it has PDFs or WARCs to process
                                has_pdfs = os.path.exists(os.path.join(subproject_path, "pdfs", "scraped-pdfs"))
                                has_warcs = os.path.exists(os.path.join(subproject_path, "warcs", "scraped-warcs"))
                                if has_pdfs or has_warcs:
                                    total_items += 1
                                    processing_items.append((project, subproject, subproject_path))
                    
                    if total_items == 0:
                        st.warning("No projects or subprojects with PDF/WARC files found.")
                        return
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    status_detail = st.empty()
                    current_item = 0
                    
                    start_time = time.time()
                    for project, subproject, subproject_path in processing_items:
                        status_text.text(f"Processing {current_item+1}/{total_items}: {project}/{subproject}")
                        
                        estimator = TokenEstimator(subproject_path)
                        
                        # Process PDFs if they exist
                        pdf_folder = os.path.join(subproject_path, "pdfs", "scraped-pdfs")
                        if os.path.exists(pdf_folder) and any(f.endswith(".pdf") for f in os.listdir(pdf_folder)):
                            status_detail.text(f"Processing PDFs in {subproject}...")
                            estimator.process_pdfs(pdf_folder)
                        
                        # Process WARCs if they exist
                        warc_folder = os.path.join(subproject_path, "warcs", "scraped-warcs")
                        if os.path.exists(warc_folder) and any(f.endswith(".warc") for f in os.listdir(warc_folder)):
                            status_detail.text(f"Processing WARCs in {subproject}...")
                            estimator.process_warcs(warc_folder)
                        
                        current_item += 1
                        elapsed = time.time() - start_time
                        eta = (elapsed / current_item) * (total_items - current_item) if current_item > 0 else 0
                        
                        progress_bar.progress(current_item / total_items)
                        status_text.text(f"Progress: {current_item}/{total_items} - ETA: {eta:.1f}s")
                    
                    elapsed = time.time() - start_time
                    status_text.text(f"Token recalculation completed in {elapsed:.1f} seconds!")
                    status_detail.text("")
                    progress_bar.progress(1.0)
                    st.success("Token recalculation completed for all projects!")
                    
                    if st.button("Refresh Dashboard"):
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Token recalculation failed: {str(e)}")
                    st.exception(e)  # Shows the full traceback

    with tab2:
        st.subheader("Collect Compressed Files")
        st.info("This operation will gather all existing compressed files from subprojects and copy them to a central project location for easier access.")
        if st.button("Collect Compressed Files", key="collect_compressed"):
            try:
                # Collect files to process
                with st.spinner("Finding compressed files..."):
                    file_tasks = []
                    projects = [p for p in os.listdir(output_root) if os.path.isdir(os.path.join(output_root, p))]
                    for project in projects:
                        project_path = os.path.join(output_root, project)
                        dest_folder = os.path.join(project_path, "0_compressed_all")
                        os.makedirs(dest_folder, exist_ok=True)
                        
                        subprojects = [sp for sp in os.listdir(project_path)
                                      if os.path.isdir(os.path.join(project_path, sp)) 
                                      and sp not in ["compressed_files", "0_compressed_all"]]
                                      
                        for subproject in subprojects:
                            subproject_path = os.path.join(project_path, subproject)
                            comp_folder = os.path.join(subproject_path, "compressed")
                            if os.path.exists(comp_folder):
                                for f in os.listdir(comp_folder):
                                    if f.endswith(".zip") or f.endswith(".warc.gz"):
                                        src_file = os.path.join(comp_folder, f)
                                        dest_file = os.path.join(dest_folder, f)
                                        # Check if file needs to be updated
                                        needs_copy = not os.path.exists(dest_file) or \
                                                    os.path.getmtime(src_file) > os.path.getmtime(dest_file) or \
                                                    os.path.getsize(src_file) != os.path.getsize(dest_file)
                                        if needs_copy:
                                            file_tasks.append((src_file, dest_file))
                
                total_tasks = len(file_tasks)
                if total_tasks == 0:
                    st.info("No new compressed files to copy.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    file_detail = st.empty()
                    
                    start_time = time.time()
                    for i, (src, dest) in enumerate(file_tasks):
                        file_detail.text(f"Copying: {os.path.basename(src)}")
                        shutil.copy2(src, dest)
                        progress_bar.progress((i+1) / total_tasks)
                        status_text.text(f"Progress: {i+1}/{total_tasks} files")
                    
                    elapsed = time.time() - start_time
                    file_detail.text("")
                    status_text.text(f"Collection completed in {elapsed:.1f} seconds!")
                    st.success(f"Collected {total_tasks} compressed files successfully!")
                    
                    if st.button("Refresh Dashboard"):
                        st.rerun()
                        
            except Exception as e:
                st.error(f"File collection operation failed: {str(e)}")
                st.exception(e)  # Shows the full traceback
