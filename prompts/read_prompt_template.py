import os
from logger_setup import logger, log_entry_exit

def read_prompt_template(template_name: str, prompts_dir: str = "prompts") -> str:
    """
    Reads a prompt template file from the specified directory and returns its contents as a string.

    Parameters
    ----------
    template_name : str
        The filename of the template (e.g., "summary_prompt.txt" or "my_prompt.md").
    prompts_dir : str, optional
        The directory containing all prompt templates. Defaults to "prompts".

    Returns
    -------
    str
        The full text of the prompt template.

    Raises
    ------
    FileNotFoundError
        If the template file does not exist in the specified directory.
    """

    logger.info(f"Reading prompt template: {template_name}")
    
    # Construct the full path to the template file
    template_path = os.path.join(prompts_dir, template_name)

    # Ensure the file exists (raises FileNotFoundError if not)
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")

    # Read and return the file’s contents
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    return content

# -------------------------------------------------------------------------
# Example usage:
if __name__ == "__main__":
    try:
        prompt_text = read_prompt_template("my_prompt.txt", "prompts")
        print("Prompt Template Content:")
        print(prompt_text)
    except FileNotFoundError as e:
        print(e)
