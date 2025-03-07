import os
import csv
import logging
import time

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_token_count_from_csv(tokens_csv_path):
    """
    Extract the total token count from a tokens.csv file.
    Handles empty or invalid files gracefully.
    
    Args:
        tokens_csv_path (str): Path to the tokens CSV file
        
    Returns:
        int: Total token count (0 if file doesn't exist or is invalid)
    """
    total_tokens = 0
    if os.path.exists(tokens_csv_path):
        try:
            with open(tokens_csv_path, "r") as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip the header safely
                for row in reader:
                    if row and row[0] not in ["TOTAL (WARCs)", "TOTAL (PDFs)"]: 
                        total_tokens += int(row[1])
        except (StopIteration, ValueError, IndexError) as e:
            logger.warning(f"Error reading tokens.csv at {tokens_csv_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error with token file {tokens_csv_path}: {e}")
    return total_tokens

def _count_files_in_directory(directory, extensions):
    """Helper function to count files with specific extensions in a directory"""
    if not os.path.exists(directory):
        return 0, 0
        
    count = 0
    total_bytes = 0
    
    try:
        for file in os.listdir(directory):
            if any(file.endswith(ext) for ext in extensions):
                file_path = os.path.join(directory, file)
                count += 1
                total_bytes += os.path.getsize(file_path)
    except Exception as e:
        logger.error(f"Error counting files in {directory}: {e}")
        
    return count, total_bytes

def get_project_level_stats(output_root):
    """
    Calculate project-level statistics (summary for all subprojects within a project).
    
    Args:
        output_root (str): Root directory containing all projects
        
    Returns:
        list: List of project statistics rows
    """
    project_data = []

    try:
        for project in os.listdir(output_root):
            project_path = os.path.join(output_root, project)
            if os.path.isdir(project_path):
                total_files = 0
                total_tokens = 0
                total_bytes = 0
                total_compressed_size = 0
                total_pdf_count = 0
                total_warc_count = 0
                
                # Get the modification time of the project directory
                last_modified = os.path.getmtime(project_path)

                # Calculate size of compressed files in project's 0_compressed_all directory
                compressed_files_dir = os.path.join(project_path, "0_compressed_all")
                if os.path.exists(compressed_files_dir):
                    for file in os.listdir(compressed_files_dir):
                        if file.endswith(".zip") or file.endswith(".warc.gz"):
                            file_path = os.path.join(compressed_files_dir, file)
                            total_compressed_size += os.path.getsize(file_path)
                            # Update last_modified if this file is more recent
                            file_mtime = os.path.getmtime(file_path)
                            if file_mtime > last_modified:
                                last_modified = file_mtime

                # Process subprojects, skipping any folder with "compressed" in its name.
                for subproject in os.listdir(project_path):
                    if "compressed" in subproject.lower():
                        continue
                    subproject_path = os.path.join(project_path, subproject)
                    if os.path.isdir(subproject_path):
                        # Check if subproject is more recently modified
                        subproj_mtime = os.path.getmtime(subproject_path)
                        if subproj_mtime > last_modified:
                            last_modified = subproj_mtime
                            
                        # PDFs
                        pdf_folder = os.path.join(subproject_path, "pdfs", "scraped-pdfs")
                        pdf_count, pdf_bytes = _count_files_in_directory(pdf_folder, [".pdf"])
                        total_pdf_count += pdf_count
                        total_files += pdf_count
                        total_bytes += pdf_bytes

                        # WARCs
                        warc_folder = os.path.join(subproject_path, "warcs", "scraped-warcs")
                        warc_count, warc_bytes = _count_files_in_directory(warc_folder, [".warc"])
                        total_warc_count += warc_count
                        total_files += warc_count
                        total_bytes += warc_bytes

                        # Tokens
                        tokens_csv_path = os.path.join(subproject_path, "tokens", "tokens.csv")
                        total_tokens += get_token_count_from_csv(tokens_csv_path)

                # Add a row summarizing the project with timestamp and counts
                project_data.append([project, total_files, total_tokens, total_compressed_size, 
                                     total_bytes, total_warc_count, total_pdf_count, last_modified])
    except Exception as e:
        logger.error(f"Error while calculating project statistics: {e}")

    return project_data

def get_subproject_level_stats(output_root):
    """
    Calculate subproject-level statistics (details for each subproject).
    
    Args:
        output_root (str): Root directory containing all projects
        
    Returns:
        list: List of subproject statistics rows
    """
    subproject_data = []

    try:
        for project in os.listdir(output_root):
            project_path = os.path.join(output_root, project)
            if os.path.isdir(project_path):
                for subproject in os.listdir(project_path):
                    # Skip any folder with "compressed" in its name.
                    if "compressed" in subproject.lower():
                        continue
                    subproject_path = os.path.join(project_path, subproject)
                    if os.path.isdir(subproject_path):
                        total_files = 0
                        total_tokens = 0
                        total_bytes = 0
                        
                        # Get the modification time of the subproject directory
                        last_modified = os.path.getmtime(subproject_path)

                        # PDFs
                        pdf_folder = os.path.join(subproject_path, "pdfs", "scraped-pdfs")
                        if os.path.exists(pdf_folder):
                            pdf_mtime = os.path.getmtime(pdf_folder)
                            if pdf_mtime > last_modified:
                                last_modified = pdf_mtime
                        pdf_count, pdf_bytes = _count_files_in_directory(pdf_folder, [".pdf"])
                        total_files += pdf_count
                        total_bytes += pdf_bytes

                        # WARCs
                        warc_folder = os.path.join(subproject_path, "warcs", "scraped-warcs")
                        if os.path.exists(warc_folder):
                            warc_mtime = os.path.getmtime(warc_folder)
                            if warc_mtime > last_modified:
                                last_modified = warc_mtime
                        warc_count, warc_bytes = _count_files_in_directory(warc_folder, [".warc"])
                        total_files += warc_count
                        total_bytes += warc_bytes

                        # Tokens
                        tokens_csv_path = os.path.join(subproject_path, "tokens", "tokens.csv")
                        total_tokens += get_token_count_from_csv(tokens_csv_path)

                        # Add a row for the subproject
                        subproject_data.append([project, subproject, total_files, total_tokens, total_bytes, last_modified])
    except Exception as e:
        logger.error(f"Error while calculating subproject statistics: {e}")

    return subproject_data
