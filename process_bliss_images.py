import os
from PIL import Image

# --- Configuration ---
# The original folder with Bliss symbols (h=1000, variable width)
source_directory = "bliss_h1000_bmp"
# The new folder where the processed, square images will be saved
destination_directory = "bliss_1000x1000_padded"


def process_images():
    """
    Reads images from the source directory. For each image, it creates a new
    canvas that is 1000px tall and wide enough to guarantee at least 100px
    of horizontal white padding on each side. The original image is centered
    on this new canvas and saved to the destination directory.
    """
    if not os.path.isdir(source_directory):
        print(f"Error: Source directory '{source_directory}' not found.")
        return

    # Create the destination directory if it doesn't exist
    os.makedirs(destination_directory, exist_ok=True)
    print(f"Processing images from '{source_directory}'...")
    print(f"Saving processed images to '{destination_directory}'...")

    processed_count = 0

    # Loop through all files in the source directory
    for filename in os.listdir(source_directory):
        if filename.lower().endswith(".bmp"):
            input_path = os.path.join(source_directory, filename)
            output_path = os.path.join(destination_directory, filename)

            try:
                # Open the image file
                with Image.open(input_path) as img:
                    width, height = img.size

                    # Determine the width of the new canvas.
                    # It must be at least 1000px wide (the height), or wider if needed
                    # to accommodate the original width plus 100px padding on each side.
                    new_canvas_width = max(height, width + 200)

                    # Create a new 1-bit monochrome canvas to keep file sizes small.
                    # Mode '1' is for 1-bit pixels, and the color `1` corresponds to white.
                    padded_canvas = Image.new("1", (new_canvas_width, height), 1)

                    # Calculate the horizontal position to center the original image
                    paste_x = (new_canvas_width - width) // 2

                    # Paste the original image onto the white canvas
                    padded_canvas.paste(img, (paste_x, 0))

                    # Save the new, padded image
                    padded_canvas.save(output_path)
                    processed_count += 1

            except Exception as e:
                print(f"  -> Could not process {filename}. Error: {e}")

    print("\n--- Processing Complete ---")
    print(f"Processed and saved {processed_count} images.")


if __name__ == "__main__":
    process_images()
