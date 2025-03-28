#!/usr/bin/env python3

import os
import filetype
from lib.page import Page, NotAnImageException
from PIL import Image
import tempfile
import argparse
from natsort import natsorted, ns
import math

parser = argparse.ArgumentParser(
                    prog='splitter',
                    description='What the program does',
                    epilog='Text at the bottom of help')
parser.add_argument('input')
parser.add_argument('output')
parser.add_argument('-r', '--recurse',
                    action='store_true')
parser.add_argument('-n', '--nofolders',
                    action='store_true')

args = parser.parse_args()

input_dir = args.input
output_dir = args.output
recurse = args.recurse
nofolders = args.nofolders

for filename in os.listdir(output_dir):
    raise Exception("output dir must be empty")

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
        img_path = os.path.join(img_dir, filename)

        kind = filetype.guess(img_path)
        if kind == None or not kind.mime.startswith("image/"):
            continue
        
        images_paths.append(img_path)

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

        panel_ys = [[panel[1], panel[3]] for panel in info["panels"]]

        merged_panels = merge_intervals(panel_ys)

        merged_panels.sort(key=lambda x: x[0])

        merged_panels[0] = [0, merged_panels[0][0] + merged_panels[0][1]]
        merged_panels[-1][-1] = total_height - merged_panels[-1][0]

        ratio = 1080 / (1920 * .4)
        max_height = max_width * ratio

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

        # print(max_height, merged_panels)
        print(split_positions)

        if recurse and not nofolders:
            output_to = os.path.join(output_dir, str(folder_i).zfill(3))
            os.makedirs(output_to)
        else:
            output_to = output_dir

        for page_i, page in enumerate(split_positions):
            position_y = int(page[0])
            height = int(page[1])

            page_img = full_strip_image.crop((0, position_y, max_width, position_y + height))

            padded_img = Image.new('RGB', (max_width, max(height, int(max_height))), color="white")
            padded_img.paste(page_img, (0,max(0, int(max_height/2 - height/2))))

            if nofolders:
                folder_prefix = str(folder_i).zfill(3) + "_"
            else:
                folder_prefix = ""

            padded_img.save(os.path.join(output_to, folder_prefix + str(page_i).zfill(3) + ".png"))

    finally:
        os.remove(full_strip_path)
