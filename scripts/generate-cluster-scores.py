#!/usr/bin/env python3
import csv
import os
import subprocess
import sys
import json
import shutil
from pathlib import Path

def convert_csv_to_similarity_scores(csv_file, output_file):
    """
    Converts a CSV file from similarity analysis to the format expected by cluster-scores.py
    
    Args:
        csv_file (str): Path to the CSV file
        output_file (str): Path to write the output file
    """
    if not os.path.exists(csv_file):
        print(f"Warning: File not found: {csv_file}")
        return False
        
    with open(csv_file, 'r') as f_in, open(output_file, 'w') as f_out:
        reader = csv.reader(f_in)
        header = next(reader, None)  # Skip header
        
        if not header:
            print(f"Warning: Empty file or no header: {csv_file}")
            return False
            
        count = 0
        for row in reader:
            if len(row) >= 3:
                file1, file2, score = row[0], row[1], row[2]
                # Format: filename,score,path
                f_out.write(f"{os.path.basename(file1)},{score},{file1}\n")
                count += 1
                
        print(f"Converted {csv_file} to {output_file} ({count} entries)")
        return True if count > 0 else False

def run_cluster_scores(script_path, working_dir, input_file, output_file, threshold=0.01):
    """Run the cluster-scores.py script"""
    if not os.path.exists(script_path):
        print(f"Error: Script not found: {script_path}")
        return False
        
    # Copy input file to working directory as similarity-scores.txt
    temp_input = os.path.join(working_dir, "similarity-scores.txt")
    if temp_input != input_file:
        shutil.copy2(input_file, temp_input)
    
    original_dir = os.getcwd()
    try:
        # Change to working directory
        os.chdir(working_dir)
        
        # Run the script
        command = ["python3", script_path, "-t", str(threshold)]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Warning: cluster-scores.py returned error: {result.returncode}")
            print(f"STDERR: {result.stderr}")
        
        # Check if clusters.json was created
        if os.path.exists("clusters.json"):
            # Copy to output file
            shutil.copy2("clusters.json", output_file)
            print(f"Generated {output_file}")
            return True
        else:
            print("Error: clusters.json not found")
            return False
    
    finally:
        os.chdir(original_dir)
        # Clean up
        if os.path.exists(temp_input) and temp_input != input_file:
            os.remove(temp_input)
        
        temp_output = os.path.join(working_dir, "clusters.json")
        if os.path.exists(temp_output):
            os.remove(temp_output)

def create_circle_json(clusters_json_path, output_file):
    """
    Create a circle.json file from a clusters.json file
    
    Args:
        clusters_json_path (str): Path to the clusters.json file
        output_file (str): Path to write the circle.json file
    """
    if not os.path.exists(clusters_json_path):
        print(f"Error: Clusters file not found: {clusters_json_path}")
        return False
    
    try:
        with open(clusters_json_path, 'r') as f:
            clusters_data = json.load(f)
        
        # Convert to circle packing format
        circle_data = {
            "name": "root",
            "children": []
        }
        
        if "children" in clusters_data:
            for i, cluster in enumerate(clusters_data["children"]):
                cluster_node = {
                    "name": f"Cluster {i+1}",
                    "children": []
                }
                
                if "children" in cluster:
                    for j, item in enumerate(cluster["children"]):
                        item_name = item.get("name", f"Item {j+1}")
                        try:
                            item_score = float(item.get("score", 0.5))
                        except (ValueError, TypeError):
                            item_score = 0.5
                        
                        cluster_node["children"].append({
                            "name": item_name,
                            "size": int(100 + item_score * 1900)
                        })
                
                circle_data["children"].append(cluster_node)
        
        with open(output_file, 'w') as f:
            json.dump(circle_data, f, indent=2)
        
        print(f"Created circle.json: {output_file}")
        return True
    
    except Exception as e:
        print(f"Error creating circle.json: {e}")
        return False

def create_d3_cluster_json(clusters_json_path, output_file):
    """
    Create a D3 cluster JSON from a clusters.json file
    
    Args:
        clusters_json_path (str): Path to the clusters.json file
        output_file (str): Path to write the D3 cluster file
    """
    if not os.path.exists(clusters_json_path):
        print(f"Error: Clusters file not found: {clusters_json_path}")
        return False
    
    try:
        with open(clusters_json_path, 'r') as f:
            clusters_data = json.load(f)
        
        # Create D3 force-directed graph format
        nodes = [{"name": "Root", "group": 1}]
        links = []
        
        if "children" in clusters_data:
            for i, cluster in enumerate(clusters_data["children"]):
                cluster_id = len(nodes)
                cluster_name = cluster.get("name", f"Cluster {i+1}")
                nodes.append({"name": cluster_name, "group": 2})
                links.append({"source": 0, "target": cluster_id, "value": 2})
                
                if "children" in cluster:
                    for j, item in enumerate(cluster["children"]):
                        item_id = len(nodes)
                        item_name = item.get("name", f"Item {j+1}")
                        nodes.append({"name": item_name, "group": 3})
                        links.append({"source": cluster_id, "target": item_id, "value": 1})
        
        d3_data = {"nodes": nodes, "links": links}
        with open(output_file, 'w') as f:
            json.dump(d3_data, f, indent=2)
        
        print(f"Created D3 cluster format: {output_file}")
        return True
        
    except Exception as e:
        print(f"Error creating D3 cluster JSON: {e}")
        return False

def main():
    # Get project paths
    project_root = Path(__file__).parent.parent
    results_dir = project_root / "similarity-results"
    tika_cluster_dir = project_root / "tika-similarity" / "tikasimilarity" / "cluster"
    
    # Create results directory if it doesn't exist
    results_dir.mkdir(exist_ok=True)
    
    # Define the similarity types to process
    similarity_types = [
        "cosine_similarity",
        "jaccard_similarity",
        "edit_value_similarity"  # Using edit_value instead of edit_distance
    ]
    
    for sim_type in similarity_types:
        print(f"\n===== Processing {sim_type} =====")
        
        # Define paths for this similarity type
        csv_file = results_dir / f"{sim_type}.csv"
        txt_file = results_dir / f"{sim_type}.txt"
        
        # Skip if CSV file doesn't exist
        if not csv_file.exists():
            print(f"Warning: CSV file not found: {csv_file}")
            continue
            
        # Step 1: Convert CSV to similarity scores format
        print(f"Converting CSV to similarity scores format")
        if not convert_csv_to_similarity_scores(str(csv_file), str(txt_file)):
            print(f"Error converting {csv_file} to similarity scores format")
            continue
        
        print(f"Running clustering scripts for {sim_type}")
        
        # Step 2: Run cluster-scores.py to generate clusters.json
        cluster_scores_script = tika_cluster_dir / "cluster-scores.py"
        clusters_json = results_dir / f"{sim_type}_clusters.json"
        print(f"  Generating clusters.json")
        run_cluster_scores(
            str(cluster_scores_script), 
            str(results_dir),
            str(txt_file),
            str(clusters_json),
            0.01  # Threshold
        )
        
        # Step 3: Create circle.json for circle packing visualization
        circle_json = results_dir / f"{sim_type}_circle.json"
        print(f"  Creating circle.json for circle packing visualization")
        create_circle_json(str(clusters_json), str(circle_json))
        
        # Step 4: Create D3 JSON for cluster visualization
        cluster_d3_json = results_dir / f"{sim_type}_cluster_d3.json"
        print(f"  Creating D3 cluster visualization format")
        create_d3_cluster_json(str(clusters_json), str(cluster_d3_json))
    
    print("\nAll JSON files generated successfully in:", results_dir)
    print("The following files can be used with visualization HTML files:")
    print("  *_clusters.json - Basic cluster visualization")
    print("  *_circle.json - Circle packing visualization")
    print("  *_cluster_d3.json - D3 cluster visualization")

if __name__ == "__main__":
    main()