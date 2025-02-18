import yaml
import json
import argparse
import argparse
from pathlib import Path
from dotenv import load_dotenv
from logger_setup import logger, log_entry_exit

from modules.create_table_sql import generate_create_table_sql 
from modules.FHIResourceManager import FHIRResourceManager 
from modules.llm_utils import get_llm


# This is the max length of the description that can be stored in BigQuery
# for either a column or a table, we did not make this a YAML parameter
# since it is a constant value
CHARACTER_LIMIT = 1024

 # Load environment variables from our .env file.
 # We store our API keys and other sensitive information in the .env file
load_dotenv()


# Function to load the schema from a JSON file
@log_entry_exit
def load_schema(schema_path):
    """Load the schema from a JSON file specified by the schema_path."""

    with open(schema_path, 'r') as f:
        return json.load(f)
    


# Function to save the enriched schema to a file
@log_entry_exit
def save_enriched_schema(enriched_schema, output_path):
    """
    If enriched_schema is a string containing JSON, parse it first so we can
    dump a proper JSON array. Otherwise, just dump directly.
    """

    # If the enriched schema is a string, attempt to parse it as JSON
    if isinstance(enriched_schema, str):

        try:
            logger.info("Attempting to parse enriched schema as JSON...")
            enriched_schema = json.loads(enriched_schema)
            logger.info("Enriched schema successfully parsed as JSON.")

        except json.JSONDecodeError:
            logger.error("Warning: Could not parse enriched_schema as JSON.")
            # If it truly isn't valid JSON, handle as needed.

    # Save the enriched schema to the output path
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(enriched_schema, f, indent=2)


@log_entry_exit
def save_final_sql(sql_statements, output_path):
    """
        This function saves the final SQL statements to the sepcified output path.

        Args:
            sql_statements (str): The SQL statements to be saved.
            output_path (str): The path where the SQL statements will be saved.
    """

    # final_sql = "".join(sql_statements)    
    
    # # Ensure SQL statements contain actual newlines,
    # # and save the file with proper formatting
    logger.info("Performing initial saving...")

    # Write the cleaned SQL code to the output file
    with open(output_path, 'w', encoding='utf-8') as outfile:
        outfile.writelines(sql_statements)
    
    logger.info("Final Save completed, cleaned SQL code saved")


@log_entry_exit
def read_yaml_file(file_path: str) -> dict:
    """
    Reads a YAML file and returns its contents as a Python dictionary.

    :param file_path: The path to the YAML file.
    :return: The contents of the YAML file as a dictionary
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data



#  ---------------------------------------------------------------------------
# This function will parse the YAML data and extract the 
# configuration information
#  ---------------------------------------------------------------------------
@log_entry_exit
def parse_yaml_data(config_data):
    """
    Parses the YAML data and extracts the configuration information.

    :param data: The YAML data to parse.
    :return: The configuration information as a dictionary
    """
    # Access the YAML information
    # Access app settings
    app_name    = config_data['app']['app_name'].strip()
    app_version = config_data['app']['app_version'].strip()

    # Access the file information
    input_schema_location  = config_data['files']['input_schema'].strip()
    output_schema_location = config_data['files']['output_schema'].strip()
    sql_output_location    = config_data['files']['sql_output'].strip()

    # Get the big query info
    project_id  = config_data['bigquery']['project_id'].strip()
    dataset_id  = config_data['bigquery']['dataset_id'].strip()
    table_id    = config_data['bigquery']['table_id'].strip()
    location    = config_data['bigquery']['location'].strip()
    mode        = config_data['bigquery']['mode'].strip()

    # Build the full table name
    full_table_name = f"{project_id}.{dataset_id}.{table_id}"

    # LLM INfo
    llm_model = config_data['llm']['model'].strip()

    # Finally, return the configuration information as a large tuple
    return app_name, app_version, input_schema_location, output_schema_location, sql_output_location, \
           project_id, dataset_id, table_id, full_table_name, location, mode, llm_model



# Main function to orchestrate the process
def main():
    """
    Parses arguments, reads YAML configuration, and orchestrates the process of
    generating enriched descriptions for FHIR schema fields and generating SQL statements
    to either create a new table, or update an existing table with ALTER statements.
    """

    # Argument parser for YAML file location
    parser = argparse.ArgumentParser(description="Generate rich descriptions for FHIR schema fields.")
    parser.add_argument('--yaml', type=str, required=True, help='The location of the YAML file')

    # Parse arguments and extract the YAML source path
    args = parser.parse_args()
    yaml_source_path = Path(args.yaml)
    logger.info(f"YAML Source Path: {yaml_source_path}")

    # Read YAML configuration file
    config_data = read_yaml_file(yaml_source_path)

    if not config_data:
        logger.error("Failed to load YAML configuration.")
        return

    # Parse the YAML data
    (
        app_name, app_version, input_schema_location, output_schema_location,
        sql_output_location, project_id, dataset_id, table_id,
        full_table_name, location, mode, llm_model
    ) = parse_yaml_data(config_data)

    # Log the parsed arguments for debugging
    indentation = ' ' * 25
    logger.info(f"Parsed YAML Arguments: \n"
            f"{indentation}input_schema_location..................: '{input_schema_location}',\n"
            f"{indentation}output_schema_location.................: '{output_schema_location}',\n"
            f"{indentation}sql_output_location....................: '{sql_output_location}',\n"
            f"{indentation}project_id.............................: '{project_id}',\n"
            f"{indentation}dateset_id.............................: '{dataset_id}',\n"
            f"{indentation}table_id...............................: '{table_id}',\n"
            f"{indentation}full_table_name........................: '{full_table_name}',\n"
            f"{indentation}location...............................: '{location}',\n"
            f"{indentation}mode...................................: '{mode}',\n"
            f"{indentation}LLM Model..............................: '{llm_model}'")


    # Initialize the Language Model (LLM)
    llm = get_llm(llm_model)

    # Load the input schema, representing the complete schema for the table
    schema = load_schema(input_schema_location)

    # Determine the corresponding FHIR resource name from the table name
    fhir_mgr = FHIRResourceManager(llm, full_table_name)
    logger.info(f"FHIR Resource Name Identified: {fhir_mgr.fhir_resource_name}")

    # Generate a table-level description for the FHIR table
    table_description = fhir_mgr.generate_table_description()
    logger.info(f"Table Description Generated...")


    # logger.info("Generating enriched schema with descriptions, using semantic chunking")
    # enriched_schema = fhir_mgr.generate_enriched_schema_with_semantic_chunking(schema)
    # logger.info("Enriched schema generation completed.")


    # Create an enriched schema with additional descriptions for each field
    logger.info("Generating enriched schema with descriptions...")
    enriched_schema = fhir_mgr.generate_enriched_schema(schema)
    logger.info("Enriched schema generation completed.")

    # Save the enriched schema to the output location
    save_enriched_schema(enriched_schema, output_schema_location)
    logger.info(f"Enriched schema successfully saved to: '{output_schema_location}'")

    # Generate SQL statements (ALTER 
    # TABLE / CREATE TABLE) based on the mode
    logger.info("Starting the SQL generation process...")
    generated_sql = fhir_mgr.generate_sql(enriched_schema, table_description, mode)
    logger.info("SQL generation completed.")

    # Save the generated SQL file
    save_final_sql(generated_sql, sql_output_location)
    logger.info(f"Generated SQL saved to: '{sql_output_location}'")

    logger.info("Process completed successfully.")

# Execute the script
if __name__ == "__main__":
    main()
