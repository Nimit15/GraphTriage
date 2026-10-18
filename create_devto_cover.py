#!/usr/bin/env python3
"""
Create a 1000x420 PNG cover image for DEV.to post.
Design: Dark slate background with connected graph illustration and centered text.
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_devto_cover():
    # Create image with exact dimensions 1000x420
    width, height = 1000, 420
    image = Image.new('RGB', (width, height), color='#0B0F19')  # Dark slate background
    draw = ImageDraw.Draw(image)

    # Try to use a decent font, fall back to default if needed
    try:
        # Try to find a good font
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf"
        ]

        title_font = None
        subtitle_font = None
        badge_font = None

        for path in font_paths:
            if os.path.exists(path):
                try:
                    title_font = ImageFont.truetype(path, 48)
                    subtitle_font = ImageFont.truetype(path, 28)
                    badge_font = ImageFont.truetype(path, 20)
                    break
                except:
                    continue

        # If no TTF font found, use default
        if title_font is None:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            badge_font = ImageFont.load_default()
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        badge_font = ImageFont.load_default()

    # Define colors
    cyan = '#06B6D4'      # Cyan for nodes
    indigo = '#6366F1'    # Indigo for nodes
    emerald = '#10B981'   # Emerald for nodes
    white = '#FFFFFF'
    light_gray = '#9CA3AF'

    # Left side: Text content (safe margin x: 60 to 820, y: 60 to 360)
    # Actually, let's use left 60% for text, right 40% for graph
    text_width = int(width * 0.6)
    graph_width = width - text_width

    # Text positioning
    text_x_start = 60
    text_y_start = 60
    line_spacing = 10

    # Top tag
    tag_text = "FALKORDB x WEMAKEDEVS GRAPH HACKS 2026"
    tag_bbox = draw.textbbox((0, 0), tag_text, font=subtitle_font)
    tag_width = tag_bbox[2] - tag_bbox[0]
    draw.text((text_x_start, text_y_start), tag_text, font=subtitle_font, fill=light_gray)

    # Main title
    title_y = text_y_start + 50
    title_text = "GraphTriage"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text((text_x_start, title_y), title_text, font=title_font, fill=white)

    # Subtitle
    subtitle_y = title_y + 70
    subtitle_text = "Graph-Grounded Incident Resolution & Temporal Agent Memory"
    subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=subtitle_font)
    subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
    draw.text((text_x_start, subtitle_y), subtitle_text, font=subtitle_font, fill=white)

    # Bottom badges
    badges_y = subtitle_y + 80
    badges = ["Track 1: Connected Data", "Track 2: Agent Memory", "OpenCypher + MCP"]
    badge_x = text_x_start

    for i, badge_text in enumerate(badges):
        # Draw badge background
        badge_padding = 8
        badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        badge_width = badge_bbox[2] - badge_bbox[0]
        badge_height = badge_bbox[3] - badge_bbox[1]

        # Alternate badge colors
        badge_colors = [
            ('#06B6D4', '#FFFFFF'),  # Cyan badge
            ('#6366F1', '#FFFFFF'),  # Indigo badge
            ('#10B981', '#FFFFFF')   # Emerald badge
        ]

        bg_color, text_color = badge_colors[i]

        # Draw rounded rectangle background (approximated)
        draw.rounded_rectangle(
            [badge_x - badge_padding, badges_y - badge_padding,
             badge_x + badge_width + badge_padding, badges_y + badge_height + badge_padding],
            radius=6,
            fill=bg_color[0] if isinstance(bg_color, tuple) else bg_color
        )

        # Draw badge text
        draw.text((badge_x, badges_y), badge_text, font=badge_font, fill=text_color)

        badge_x += badge_width + 20  # Space between badges

    # Right side: Graph illustration
    graph_x_start = text_width + 40  # Start after text area with padding
    graph_y_start = 80
    graph_width_actual = width - graph_x_start - 40
    graph_height_actual = height - graph_y_start - 40

    # Draw connected graph nodes and edges
    # Create a simple network illustration

    # Node positions (relative to graph area)
    nodes = [
        {"x": 0.2, "y": 0.3, "color": cyan, "label": "Module"},
        {"x": 0.5, "y": 0.2, "color": indigo, "label": "Function"},
        {"x": 0.8, "y": 0.4, "color": emerald, "label": "Test"},
        {"x": 0.3, "y": 0.7, "color": cyan, "label": "Function"},
        {"x": 0.6, "y": 0.6, "color": indigo, "label": "Module"},
        {"x": 0.1, "y": 0.6, "color": emerald, "label": "Function"}
    ]

    # Convert relative positions to absolute
    for node in nodes:
        node["abs_x"] = graph_x_start + (node["x"] * graph_width_actual)
        node["abs_y"] = graph_y_start + (node["y"] * graph_height_actual)
        node["radius"] = 20

    # Draw edges (connections)
    edges = [
        (0, 1), (0, 3), (1, 2), (1, 4), (2, 5), (3, 4), (4, 5)
    ]

    for start_idx, end_idx in edges:
        start_node = nodes[start_idx]
        end_node = nodes[end_idx]
        draw.line([
            (start_node["abs_x"], start_node["abs_y"]),
            (end_node["abs_x"], end_node["abs_y"])
        ], fill=white, width=3)

    # Draw nodes
    for node in nodes:
        # Draw node circle
        draw.ellipse([
            (node["abs_x"] - node["radius"], node["abs_y"] - node["radius"]),
            (node["abs_x"] + node["radius"], node["abs_y"] + node["radius"])
        ], fill=node["color"])

        # Draw node label (small text)
        label_bbox = draw.textbbox((0, 0), node["label"], font=badge_font)
        label_width = label_bbox[2] - label_bbox[0]
        label_height = label_bbox[3] - label_bbox[1]
        draw.text(
            (node["abs_x"] - label_width//2, node["abs_y"] + node["radius"] + 5),
            node["label"],
            font=badge_font,
            fill=white
        )

    # Add some connecting lines to show it's a network
    # Draw a few dotted/connector lines
    for i in range(len(nodes)):
        for j in range(i+1, len(nodes)):
            if (i, j) not in [(0,1), (0,3), (1,2), (1,4), (2,5), (3,4), (4,5)]:
                # Occasionally draw faint connections
                if (i + j) % 3 == 0:  # Only some connections
                    start_node = nodes[i]
                    end_node = nodes[j]
                    draw.line([
                        (start_node["abs_x"], start_node["abs_y"]),
                        (end_node["abs_x"], end_node["abs_y"])
                    ], fill=light_gray, width=1)

    # Save the image
    output_path = os.path.join(os.path.dirname(__file__), 'devto_cover.png')
    image.save(output_path, 'PNG')
    print(f"Cover image saved to: {output_path}")
    print(f"Dimensions: {image.size}")

    return output_path

if __name__ == "__main__":
    create_devto_cover()