#!/usr/bin/env python3

import os
import filetype
from lib.page import Page, NotAnImageException
from PIL import Image
import tempfile
import argparse
from natsort import natsorted, ns
import math
import subprocess

parser = argparse.ArgumentParser(
                    prog='splitter',
                    description='What the program does',
                    epilog='Text at the bottom of help')
parser.add_argument('input')
parser.add_argument('output')
parser.add_argument('-s', '--scroll-large', action='store_true')
parser.add_argument('-r', '--recurse',
                    action='store_true')
parser.add_argument('-n', '--no-folders',
                    action='store_true')
parser.add_argument('-d', '--remove-duplicates',
                    action='store_true')
parser.add_argument('-w', '--width',
                    default=50, type=int)

args = parser.parse_args()

input_dir = args.input
output_dir = args.output
scroll_large = args.scroll_large
recurse = args.recurse
nofolders = args.no_folders
remove_duplicates = args.remove_duplicates
target_width = args.width

for filename in os.listdir(output_dir):
    raise Exception("output dir must be empty")

ignore_files = []
if remove_duplicates:
    fdupes_command = ["fdupes", input_dir]
    if recurse:
        fdupes_command.append("-r")
    fdupes_output = str(subprocess.check_output(fdupes_command))
    for group_text in fdupes_output.split("\\n\\n"):
        group = group_text.split("\\n")
        group = [os.path.realpath(path) for path in group]
        if len(group) >= 10:
            ignore_files += group[1:]

if recurse:
    input_folders = []
    for foldername in os.listdir(input_dir):
        folder_path = os.path.join(input_dir, foldername)
        if os.path.isdir(folder_path):
            input_folders.append(folder_path)
    input_folders.sort(key = lambda folder_path : int(os.path.basename(folder_path).split(" Ch. ")[1]))
else:
    input_folders = [input_dir]

def merge_intervals(intervals):
    # Sort intervals by starting position
    intervals.sort(key=lambda x: x[0])
    merged = []

    for current in intervals:
        # If merged is empty or no overlap, add current interval
        if not merged or merged[-1][0] + merged[-1][1] < current[0]:
            merged.append(current)
        else:
            # Merge the current interval with the last one
            last = merged[-1]
            merged[-1] = [last[0], max(last[0] + last[1], current[0] + current[1]) - last[0]]

    return merged

for folder_i, img_dir in enumerate(input_folders):
    print(img_dir)

    images_paths = []
    for filename in os.listdir(img_dir):
        img_path = os.path.realpath(os.path.join(img_dir, filename))

        kind = filetype.guess(img_path)
        if kind == None or not kind.mime.startswith("image/") or img_path in ignore_files:
            continue
        
        images_paths.append(img_path)

    if recurse and not nofolders:
        output_to = os.path.join(output_dir, str(folder_i).zfill(3))
        os.makedirs(output_to)
    else:
        output_to = output_dir

    if nofolders:
        folder_prefix = str(folder_i).zfill(3) + "_"
    else:
        folder_prefix = ""
    

    images_paths = natsorted(images_paths)

    images_original = [Image.open(img_path) for img_path in images_paths]

    widths, heights = zip(*(i.size for i in images_original))
    max_width = max(widths)
    total_height = sum(heights)

    try:
        full_strip_path = tempfile.mkstemp(suffix=".png")[1]
        # print(full_strip_path)

        full_strip_image = Image.new('RGB', (max_width, total_height), color="white")
        y_offset = 0
        for im in images_original:
            full_strip_image.paste(im, (0,y_offset))
            y_offset += im.size[1]

        full_strip_image.save(full_strip_path)

        page = Page(
            full_strip_path,
            numbering = "ltr",
            url = None,
            min_panel_size_ratio = None,
            panel_expansion = True,
        )

        info = page.get_infos()

        # for page_i, page in enumerate(info["panels"]):
        #     page_img = full_strip_image.crop((page[0], page[1], page[0] + page[2], page[1] + page[3]))
        #     page_img.save(os.path.join(output_to, "panel_" + folder_prefix + str(page_i).zfill(3) + ".png"))

        panel_ys = [[panel[1], panel[3]] for panel in info["panels"]]

        merged_panels = merge_intervals(panel_ys)

        merged_panels.sort(key=lambda x: x[0])

        # for page_i, page in enumerate(merged_panels):
        #     page_img = full_strip_image.crop((0, int(page[0]), max_width, int(page[0]) + int(page[1])))
        #     page_img.save(os.path.join(output_to, "merged_panel_" + folder_prefix + str(page_i).zfill(3) + ".png"))

        ratio = 1080 / (1920 * (target_width / 100))
        max_height = int(max_width * ratio)

        merged_panels_split_solid = []
        pixels = full_strip_image.load()
        min_whitespace = int(max_height / 40)
        for panel in merged_panels:
            uniform_rows = []
            for y in range(panel[0], panel[0] + panel[1]):
                first_color = pixels[0, y]
                if all(all(abs(pixels[x, y][z] - first_color[z]) < 20 for z in range(3)) for x in range(max_width)):
                    if len(uniform_rows) == 0 or uniform_rows[-1][0] + uniform_rows[-1][1] != y:
                        uniform_rows.append([y, 1])
                    else:
                        uniform_rows[-1][1] += 1

            uniform_rows = [uniform_row for uniform_row in uniform_rows if uniform_row[1] >= min_whitespace]
            
            if len(uniform_rows) == 0:
                merged_panels_split_solid.append(panel)
            else:
                current_y = panel[0]
                for uniform_row in uniform_rows:
                    if current_y != uniform_row[0]:
                        merged_panels_split_solid.append([current_y, uniform_row[0] - current_y])
                    current_y = uniform_row[0] + uniform_row[1]
                if current_y != panel[0] + panel[1]:
                    merged_panels_split_solid.append([current_y, panel[0] + panel[1] - current_y])
        merged_panels = merged_panels_split_solid

        # for page_i, page in enumerate(merged_panels):
        #     page_img = full_strip_image.crop((0, int(page[0]), max_width, int(page[0]) + int(page[1])))
        #     page_img.save(os.path.join(output_to, "split_panel_" + folder_prefix + str(page_i).zfill(3) + ".png"))

        max_whitespace = int(max_height / 6)
        panels_and_whitespace = []
        current_y = 0
        for panel in merged_panels:
            if panel[0] != current_y:
                whitespace_size = panel[0] - current_y
                if whitespace_size > max_whitespace:
                    panels_and_whitespace.append([current_y, whitespace_size])
            panels_and_whitespace.append(panel)
            current_y = panel[0] + panel[1]
        if total_height != current_y:
            whitespace_size = total_height - current_y
            if whitespace_size > max_whitespace:
                panels_and_whitespace.append([current_y, whitespace_size])
        merged_panels = panels_and_whitespace

        # for page_i, page in enumerate(merged_panels):
        #     page_img = full_strip_image.crop((0, int(page[0]), max_width, int(page[0]) + int(page[1])))
        #     page_img.save(os.path.join(output_to, "panel_with_whitespace" + folder_prefix + str(page_i).zfill(3) + ".png"))

        merged_panels[0] = [0, merged_panels[0][0] + merged_panels[0][1]]
        merged_panels[-1][-1] = total_height - merged_panels[-1][0]

        current_y = 0
        split_positions = []
        remaining_panels = merged_panels
        while len(remaining_panels) > 0:
            page = []
            for remaining_panel in remaining_panels:
                if remaining_panel[0] + remaining_panel[1] <= current_y + max_height:
                    page.append(remaining_panel)
                else:
                    break
            
            if len(page) == 0 and len(remaining_panels) > 0:
                page.append(remaining_panels[0])
            
            remaining_panels = remaining_panels[len(page):]
            
            if len(remaining_panels) == 0:
                cutoff = total_height
                #print("final")
            else:
                end_of_panels = page[-1][0] + page[-1][1]
                if end_of_panels - current_y > max_height:
                    #print("panel too long")
                    cutoff = end_of_panels
                else:
                    start_of_next_panels = remaining_panels[0][0]
                    ideal_cutoff = int((end_of_panels + start_of_next_panels)/2)
                    if ideal_cutoff > current_y + max_height:
                        #print("not ideal")
                        cutoff = current_y + max_height
                    else:
                        #print("ideal")
                        cutoff = ideal_cutoff
            
            split_positions.append([current_y, cutoff-current_y])
            current_y = cutoff
        
        if scroll_large:
            split_positions_original = split_positions
            split_positions = []
            for page in split_positions_original:
                if page[1] > max_height:
                    scroll_size = int(max_height * .4)
                    current_y = page[0]
                    while current_y + max_height <= page[0] + page[1]:
                        split_positions.append([current_y, max_height])
                        current_y += scroll_size
                    split_positions.append([page[0] + page[1] - max_height, max_height])
                else:
                    split_positions.append(page)

        # print(max_height, merged_panels)
        print(split_positions)

        for page_i, page in enumerate(split_positions):
            position_y = int(page[0])
            height = int(page[1])

            page_img = full_strip_image.crop((0, position_y, max_width, position_y + height))

            padded_img = Image.new('RGB', (max_width, max(height, int(max_height))), color="white")
            padded_img.paste(page_img, (0,max(0, int(max_height/2 - height/2))))
            
            padded_img.save(os.path.join(output_to, folder_prefix + str(page_i).zfill(3) + ".png"))

    finally:
        os.remove(full_strip_path)
