import argparse
import json
import os
import time
import pandas as pd  # Ensure pandas is imported
from openpyxl import Workbook  # Import openpyxl for Excel support

import pandas as pd


def save_to_json(data, directory, filename):
    # Ensure the specified directory exists
    os.makedirs(directory, exist_ok=True)
    # Define the full path for the JSON file
    filepath = os.path.join(directory, filename)
    # Write the data to a JSON file
    with open(filepath, "w") as json_file:
        json.dump(data, json_file, indent=4)


def videofn_to_idx(humanml_df, prefix_to_add):
    # Initialize an empty dictionary to store video filenames and their
    # corresponding indices
    videofn2idx_dict = {}
    # Initialize an empty dictionary to store indices and their
    # corresponding video filenames
    idx2videofn_dict = {}
    for index, row in humanml_df.iterrows():
        # Get the raw video filename from the dataframe
        raw_video_fn = row["source_path"]
        # Construct the new video filename with the prefix
        video_fn = prefix_to_add + "_".join(raw_video_fn.split(".")[1].split("/")[2:])
        # Extract the index from the new name
        idx = row["new_name"].split(".")[0]
        # Print the mapping of index to video filename
        print(f"{idx} -> {video_fn}")
        # Add the mapping to the videofn2idx_dict
        videofn2idx_dict[video_fn] = idx
        # Add the mapping to the idx2videofn_dict
        idx2videofn_dict[idx] = video_fn

    # Return the two dictionaries
    return videofn2idx_dict, idx2videofn_dict


def get_all_verb_list(txt_dscpt_fdpath):
    verb_list = []
    # Initialize an empty dictionary to store verbs and their
    # sentence/frequency info
    verb_dict = {}
    # Initialize an empty dictionary to store file indices and their
    # corresponding verbs
    idx2verb = {}

    for file in os.listdir(txt_dscpt_fdpath):
        # Ensure the file is a text file
        assert file.endswith(".txt")
        # Extract the file name without extension (idx)
        file_idx = file.split(".")[0]

        with open(os.path.join(txt_dscpt_fdpath, file), "r") as f:
            # Track verbs in the current file to avoid duplicates in idx2verb
            file_verbs = set()

            # Read the file line by line
            for line in f:
                # Split the line to extract the part with word and POS tags
                words_with_tags = line.strip().split("#")[1]
                # Split by space to get individual word/tag pairs
                words = words_with_tags.split(" ")

                # Iterate through each word and its corresponding POS tag
                for word_tag in words:
                    # Split word and tag by '/'
                    word, tag = word_tag.split("/")
                    # If the tag is 'VERB'
                    if tag == "VERB":
                        if word not in verb_list:
                            # Add the verb to the list
                            verb_list.append(word)

                        # Initialize or update the verb's
                        # entry in the dictionary
                        if word not in verb_dict:
                            # Initialize the frequency, sentences, and idx list
                            verb_dict[word] = {"freq": 0, "sentences": [], "idx": []}

                        # Increment the frequency
                        verb_dict[word]["freq"] += 1
                        # Add the sentence to the list
                        verb_dict[word]["sentences"].append(line.strip().split("#")[0])
                        if file_idx not in verb_dict[word]["idx"]:
                            # Add the file index (without extension)
                            verb_dict[word]["idx"].append(file_idx)

                        # Add the verb to the set of verbs for the current file
                        file_verbs.add(word)

            # After processing all lines in the file,
            # update idx2verb with the verbs from this file
            idx2verb[file_idx] = list(file_verbs)

    return verb_list, verb_dict, idx2verb


def check_dscpt_exist(idx2videofn, txt_dscpt_fdpath):
    num_missing = 0
    # check if the number of descriptions is the same as the number of videos
    assert len(idx2videofn.keys()) == len(os.listdir(txt_dscpt_fdpath))
    for idx, videofn in idx2videofn.items():
        if not os.path.exists(os.path.join(txt_dscpt_fdpath, idx + ".txt")):
            print(f"Description of {videofn} does not exist")
            num_missing += 1

    print(f"{num_missing} files are missing")


def get_videofn_info(videofn2idx, txt_dscpt_fdpath):
    # Initialize the dictionary to hold video information
    videofn_info_dict = {}

    # Iterate through each video file name in videofn2idx
    for videofn, idx in videofn2idx.items():
        # Construct the path to the corresponding description file
        txt_file_path = os.path.join(txt_dscpt_fdpath, f"{idx}.txt")

        # If the description file exists, process it
        if os.path.exists(txt_file_path):
            # Initialize a dictionary to store information for this video
            video_info = {
                "idx": idx,
                # List of verbs present in the video
                "verbs": [],
                # All sentences in the description
                "sentences": [],
            }

            # Read the description file
            with open(txt_file_path, "r") as f:
                for line in f:
                    # Extract the sentence part (before '#')
                    sentence = line.strip().split("#")[0]
                    # Add the sentence to the list of sentences
                    video_info["sentences"].append(sentence)
                    # Extract verbs from the part after '#'
                    words_with_tags = line.strip().split("#")[1]
                    words = words_with_tags.split(" ")
                    for word_tag in words:
                        word, tag = word_tag.split("/")
                        # Check if the tag is a verb
                        if tag == "VERB":
                            # Add the verb to the list of verbs
                            video_info["verbs"].append(word)

            # Add the video information to the final dictionary
            videofn_info_dict[videofn] = video_info

    return videofn_info_dict


def export_verbs_to_excel(verb_list, verb_dict, output_dir, filename="verbs.xlsx"):
    # Create a DataFrame with the verb list
    df = pd.DataFrame(verb_list, columns=["verb"])
    # Add a 'category' column with predefined options 'easy' and 'hard'
    df["category"] = pd.Categorical(
        values=[""] * len(df),  # Initialize with empty strings
        categories=["easy", "medium", "hard", "unknown", "N/A"],  # Restrict options
        ordered=False
    )
    # Add a 'frequency' column using verb_dict
    df["freq_sentce"] = df["verb"].apply(lambda verb: verb_dict.get(verb, {}).get("freq", 0))
    df["freq_video"] = df["verb"].apply(lambda verb: len(verb_dict.get(verb, {}).get("idx", [])))
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    # Define the full path for the Excel file
    filepath = os.path.join(output_dir, filename)
    # Write the DataFrame to an Excel file
    df.to_excel(filepath, index=False)


def save_sentences_to_txt(videofn_info, output_dir, filename="sentences.txt"):
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    # Define the full path for the text file
    filepath = os.path.join(output_dir, filename)
    
    # Open the file in write mode
    with open(filepath, "w") as file:
        # Iterate over each video information
        for video_info in videofn_info.values():
            # Write each sentence to the file
            for sentence in video_info["sentences"]:
                file.write(sentence + "\n")


if __name__ == "__main__":
    # Record the start time
    start_time = time.time()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--humanml3d_csv_path",
        type=str,
        default="/cpfs01/user/qiuzherui/repo/learn/humanml_motion/index.csv",
    )
    # parser.add_argument("--video_path", type=str, default="video/humanml3d")
    parser.add_argument(
        "--txt_dscpt_fdpath",
        type=str,
        default="/cpfs01/user/qiuzherui/repo/learn/humanml_motion/humanml",
    )
    parser.add_argument("--prefix_to_add", type=str, default="0-")
    parser.add_argument(
        "--output_dir", type=str, default="stat", help="Directory to save JSON files"
    )
    args = parser.parse_args()

    humanml3d_df = pd.read_csv(args.humanml3d_csv_path)
    videofn2idx, idx2videofn = videofn_to_idx(humanml3d_df, args.prefix_to_add)
    check_dscpt_exist(idx2videofn, args.txt_dscpt_fdpath)

    verb_list, verb_dict, idx2verb = get_all_verb_list(args.txt_dscpt_fdpath)
    # Sort verbs by frequency in descending order
    sorted_verbs = sorted(
        verb_dict.items(), key=lambda item: item[1]["freq"], reverse=True
    )

    # Print sorted verbs and their frequencies
    for verb, details in sorted_verbs:
        if details["freq"] > 10:
            print(f"{verb} -> {details['freq']}")

    videofn_info = get_videofn_info(videofn2idx, args.txt_dscpt_fdpath)

    # Save dictionaries to JSON files
    save_to_json(videofn2idx, args.output_dir, "videofn2idx.json")
    save_to_json(idx2videofn, args.output_dir, "idx2videofn.json")
    save_to_json(verb_dict, args.output_dir, "verb_dict.json")
    save_to_json(idx2verb, args.output_dir, "idx2verb.json")
    save_to_json(videofn_info, args.output_dir, "videofn_info.json")
    # Export verb list to Excel
    export_verbs_to_excel(verb_list, verb_dict, args.output_dir)
    # Save sentences to text file
    save_sentences_to_txt(videofn_info, args.output_dir)

    # Record the end time
    end_time = time.time()
    # Print the execution time
    print(f"Done. Time Elapsed: {end_time - start_time:.2f} seconds")
