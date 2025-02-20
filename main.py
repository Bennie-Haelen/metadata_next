import yaml
import json
import argparse
import fnmatch
import os
from dotenv import load_dotenv
from logger_setup import logger, log_entry_exit
from google.cloud import bigquery
from modules.EnrichedSchemaManager import EnrichedSchemaManager 
from modules.BigQuerySchemaManager import BigQuerySchemaManager
from modules.llm_utils import get_llm
from modules.file_utils import read_from_gcs, write_to_gcs, check_tracker_file, update_tracker_file, delete_tracker_file


# This is the max length of the description that can be stored in BigQuery
# for either a column or a table, we did not make this a YAML parameter
# since it is a constant value
CHARACTER_LIMIT = 1024
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
 # Load environment variables from our .env file.
 # We store our API keys and other sensitive information in the .env file
load_dotenv()

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
    table_description_prompt_template = config_data['files']['table_description_prompt_template'].strip()
    schema_description_prompt_template = config_data['files']['schema_description_prompt_template'].strip()
    output_gcs_location    = config_data['files']['output_gcs_location'].strip()

    # Get the big query info
    bq_job_project_id = config_data['bigquery']['job']['project_id'].strip()
    bq_job_location   = config_data['bigquery']['job']['location'].strip()
    source_config = config_data['bigquery']['source']
    bq_source_project_id = source_config['project_id'].strip()
    bq_source_dataset_id = source_config['dataset_id'].strip()
    bq_source_table_id = source_config.get('table_id', "")
    bq_source_exclusion_list = source_config.get('exclusion_list', "")
    destination_config = config_data['bigquery']['destination']
    bq_destination_project_id = destination_config['project_id'].strip()
    bq_destination_dataset_id = destination_config['dataset_id'].strip()
    bq_destination_table_prefix = destination_config.get('table_prefix', None)
    bq_destination_table_suffix = destination_config.get('table_suffix', None)
    mode        = config_data['bigquery']['mode'].strip()

    # LLM INfo
    llm_model = config_data['llm']['model'].strip()

    # Finally, return the configuration information as a large tuple
    return app_name, app_version, table_description_prompt_template, schema_description_prompt_template, \
            output_gcs_location, bq_job_project_id, bq_job_location, bq_source_project_id, bq_source_dataset_id, bq_source_table_id, bq_source_exclusion_list, \
            bq_destination_project_id, bq_destination_dataset_id, bq_destination_table_prefix, bq_destination_table_suffix, mode, llm_model

@log_entry_exit
def list_bigquery_tables(job_project_id, job_location, source_project_id, source_dataset_id, source_table_id, exclusion_list):
    """
    Lists the BigQuery tables in the specified dataset, optionally filtering by table_id and exclusion_list.
    """
    # Load the BigQuery client
    client = bigquery.Client(project=job_project_id, location=job_location)
    
    dataset_ref = f"{source_project_id}.{source_dataset_id}"
    logger.info(f"Listing tables in dataset: '{dataset_ref}'")
    tables = list(client.list_tables(dataset_ref))
    
    # Extract only native and external tables
    valid_types = {"TABLE","EXTERNAL"}
    tables = [table for table in tables if table.table_type in valid_types]
    
    # Get table names
    table_names = {table.table_id for table in tables}
    # Process table_id field
    table_id = source_table_id
    if isinstance(table_id, str):
        if "*" in table_id:  # Wildcard pattern
            filtered_tables = {t for t in table_names if fnmatch.fnmatch(t, table_id)}
        elif table_id:  # Exact table name
            filtered_tables = {table_id} if table_id in table_names else set()
        else:  # Empty value, select all tables
            filtered_tables = table_names
    elif isinstance(table_id, list):
        filtered_tables = set(table_id) & table_names  # Ensure only existing tables are considered
    else:
        raise ValueError("Invalid table_id value")
    # Process table_exclusion_list field
    table_exclusion_list = exclusion_list
    if isinstance(table_exclusion_list, str):
        if "*" in table_exclusion_list:  # Wildcard pattern
            exclusion_set = {t for t in table_names if fnmatch.fnmatch(t, table_exclusion_list)}
        elif table_exclusion_list:  # Exact table name
            exclusion_set = {table_exclusion_list}
        else:  # Empty value, no exclusions
            exclusion_set = set()
    elif isinstance(table_exclusion_list, list):
        exclusion_set = set(table_exclusion_list) & table_names  # Ensure only existing tables are excluded
    else:
        raise ValueError("Invalid table_exclusion_list value")
    
    # Exclude tables from exclusion list
    final_tables = list(filtered_tables - exclusion_set)
    
    return final_tables

# Main function to orchestrate the process
def main():
    """
    Parses arguments, reads YAML configuration, and orchestrates the process of
    generating enriched descriptions for schema fields and generating SQL statements
    to either create a new table, or update an existing table with ALTER statements.
    """

    # Argument parser for YAML file location
    parser = argparse.ArgumentParser(description="Generate rich descriptions for schema fields.")
    parser.add_argument('--yaml', type=str, required=True, help='The location of the YAML file')

    # Parse arguments and extract the YAML source path
    args = parser.parse_args()
    yaml_source_path = args.yaml
    logger.info(f"YAML Source Path: {yaml_source_path}")

    # Read YAML configuration file
    
    config_data = read_from_gcs(yaml_source_path)
    if not config_data:
        logger.error("Failed to load YAML configuration.")
        raise ValueError("Failed to load YAML configuration.")
    else:
        config_data = yaml.safe_load(config_data)
        logger.info("YAML configuration loaded successfully.")
        
    # Parse the YAML data
    (
        app_name, app_version, table_description_prompt_template, schema_description_prompt_template,  \
            output_gcs_location, bq_job_project_id, bq_job_location, bq_source_project_id, bq_source_dataset_id, bq_source_table_id, bq_source_exclusion_list, \
            bq_destination_project_id, bq_destination_dataset_id, bq_destination_table_prefix, bq_destination_table_suffix, mode, llm_model
    ) = parse_yaml_data(config_data)

    # Log the parsed arguments for debugging
    indentation = ' ' * 25
    logger.info(f"Parsed YAML Arguments: \n"
            f"{indentation}table_description_prompt_template....................: '{table_description_prompt_template}',\n"
            f"{indentation}schema_description_prompt_template....................: '{schema_description_prompt_template}',\n"
            f"{indentation}output_gcs_location....................: '{output_gcs_location}',\n"
            f"{indentation}source_project_id.............................: '{bq_source_project_id}',\n"
            f"{indentation}source_dateset_id.............................: '{bq_source_dataset_id}',\n"
            f"{indentation}source_table_id.............................: '{bq_source_table_id}',\n"
            f"{indentation}source_exclusuon_list.............................: '{bq_source_exclusion_list}',\n"
            f"{indentation}destination_project_id.............................: '{bq_destination_project_id}',\n"
            f"{indentation}destination_dataset_id.............................: '{bq_destination_dataset_id}',\n"
            f"{indentation}destination_table_prefix.............................: '{bq_destination_table_prefix}',\n"
            f"{indentation}destination_table_suffix.............................: '{bq_destination_table_suffix}',\n"
            f"{indentation}bq_job_project_id.............................: '{bq_job_project_id}',\n"
            f"{indentation}bq_job_location.............................: '{bq_job_location}',\n"
            f"{indentation}mode...................................: '{mode}',\n"
            f"{indentation}LLM Model..............................: '{llm_model}'")


    # Initialize the Language Model (LLM)
    llm = get_llm(llm_model,GOOGLE_API_KEY)

    # Fetch the list of tables to be processed in the source dataset
    logger.info("Fetching the list of tables to be processed...")
    table_list = list_bigquery_tables(bq_job_project_id, bq_job_location, bq_source_project_id, bq_source_dataset_id, bq_source_table_id, bq_source_exclusion_list)
    logger.info(f"Tables to be processed: {table_list}")
    
    if table_list:
        tracker_file = f"{output_gcs_location}/{bq_source_project_id}/{bq_source_dataset_id}/tracker.json"
        table_description_prompt_template_str = read_from_gcs(table_description_prompt_template).encode('utf-8').decode('utf-8')
        logger.info(f"Table Description Prompt Template: {table_description_prompt_template_str}")
        schema_description_prompt_template_str = read_from_gcs(schema_description_prompt_template).encode('utf-8').decode('utf-8')
        logger.info(f"Schema Description Prompt Template: {schema_description_prompt_template_str}")
        if not table_description_prompt_template_str or not schema_description_prompt_template_str:
            logger.error("Failed to load prompt templates.")
            raise ValueError("Failed to load prompt templates.")
        logger.info("Prompt templates loaded successfully.")
        for table_id in table_list:
            # Check if the table has already been processed
            if check_tracker_file(tracker_file, table_id):
                logger.info(f"Skipping table '{table_id}' as it was already processed")
                continue
        
            # Build the full table name
            full_table_name = f"{bq_source_project_id}.{bq_source_dataset_id}.{table_id}"
            logger.info(f"Processing table: '{full_table_name}'")
            bq_mgr = BigQuerySchemaManager(bq_job_project_id, bq_job_location)
            gcs_table_location = f"{output_gcs_location}/{bq_source_project_id}/{bq_source_dataset_id}/{table_id}"
            bq_schema = bq_mgr.get_table_schema(full_table_name, "JSON")
            logger.info(f"BigQuery Schema fetched successfully for table: '{full_table_name}'")

            logger.info(f"Saving BigQuery Schema to: '{gcs_table_location}/schema.json'")
            write_to_gcs(f"{gcs_table_location}/schema.json", json.dumps(bq_schema, indent=4), 'JSON')
            logger.info(f"BigQuery Schema successfully saved to: '{gcs_table_location}/schema.json'")

            schema = json.loads(bq_schema)  # Convert schema to a dictionary

            # Determine the corresponding resource name from the table name
            destination_full_table_name = f"{bq_destination_project_id}.{bq_destination_dataset_id}.{table_id}"
            enr_schema_mgr = EnrichedSchemaManager(llm, destination_full_table_name, bq_destination_table_prefix, bq_destination_table_suffix)
            logger.info(f"Resource Name Identified: {enr_schema_mgr.resource_name}")
            logger.info(f"Destination Full Table Name: {enr_schema_mgr.full_table_name}")

            # Generate a table-level description for the table
            table_description = enr_schema_mgr.generate_table_description(table_description_prompt_template_str)
            logger.info(f"Table Description Generated...")

            logger.info("Generating enriched schema with descriptions, using semantic chunking")
            enriched_schema = enr_schema_mgr.generate_enriched_schema_with_semantic_chunking(schema, schema_description_prompt_template_str)
            logger.info("Enriched schema generation completed.")

            # Save the enriched schema to the output location
            if isinstance(enriched_schema, str):
                try:
                    enriched_schema = json.loads(enriched_schema)
                except json.JSONDecodeError:
                    logger.error("Enriched schema is not valid JSON.")
                    raise ValueError("Enriched schema is not valid JSON.")
            
            logger.info(f"Saving enriched schema to: '{gcs_table_location}/enriched_schema.json'")
            write_to_gcs(f"{gcs_table_location}/enriched_schema.json", json.dumps(enriched_schema, indent=4), 'JSON')
            logger.info(f"Enriched schema successfully saved to: '{gcs_table_location}/enriched_schema.json'")
            

            # Generate SQL statements (ALTER 
            # TABLE / CREATE TABLE) based on the mode
            logger.info("Starting the SQL generation process...")
            generated_sql = enr_schema_mgr.generate_sql(enriched_schema, table_description, mode)
            logger.info("SQL generation completed.")

            # Save the generated SQL file
            logger.info(f"Saving generated SQL to: '{gcs_table_location}/{mode.lower()}_ddl.sql'")
            write_to_gcs(f"{gcs_table_location}/{mode.lower()}_ddl.sql", generated_sql, 'text/plain')
            logger.info(f"Generated SQL saved to: '{gcs_table_location}/{mode.lower()}_ddl.sql'")

            # Update the tracker file
            logger.info(f"Updating the tracker file for table: '{table_id}'")
            update_tracker_file(tracker_file, table_id)
            logger.info(f"Tracker file updated successfully for table: '{table_id}'")
            logger.info("Process completed successfully.")
        # Delete the tracker file if all tables have been processed
        logger.info("All tables have been processed successfully.")
        logger.info("Deleting the tracker file...")
        delete_tracker_file(tracker_file)
        logger.info("Tracker file deleted successfully.")
    else:
        logger.error("No tables found in the source dataset")
    

# Execute the script
if __name__ == "__main__":
    main()
