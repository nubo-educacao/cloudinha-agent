import os

def load_instruction_from_file(filename):
    """
    Loads instruction text from a file located in the 'util' subdirectory.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "util", filename)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Instruction file not found at: {file_path}")
    except Exception as e:
        raise Exception(f"Error reading instruction file {filename}: {e}")
