import json
import tiktoken  
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain.schema import HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from prompts.read_prompt_template import read_prompt_template
from prompts import prompt_names
from logger_setup import logger, log_entry_exit

# This is the max length of the description that can be stored in BigQuery
# for either a column or a table, we did not make this a YAML parameter
# since it is a constant value
CHARACTER_LIMIT = 1024

CHUNK_SIZE = 15

class FHIRResourceManager:
    """
    This class encapsulates the functionality to manage FHIR resources in the context of BigQuery tables.
    """

    @log_entry_exit
    def __init__(self, llm, full_table_name):
        """
        Initializes the FHIRResourceManager instance.

        Parameters:
        - llm: The language model instance. Used for LLM processing in the class.
        - full_table_name (str): The fully qualified BigQuery table name in the format 
          "project.dataset.table_name".

        Attributes:
        - self.llm_model: Stores the provided language model instance.
        - self._fhir_resource_name: Extracts and stores the FHIR resource name derived 
                                    from the provided BigQuery table name.
        - self._full_table_name: Stores the provided full table name.
        """

        # Store the provided language model instance
        self.llm_model = llm  

        # Store the provided full table name
        self._full_table_name = full_table_name

        # Extract and store the FHIR resource name
        self._fhir_resource_name = self._extract_fhir_resource_name(full_table_name) 



    @property
    def fhir_resource_name(self):
        """
        Read-only property to access the FHIR resource name.

        This property provides access to the extracted FHIR resource name without allowing 
        direct modification. The value is set during object initialization and retrieved when accessed.

        Returns:
        - str: The extracted FHIR resource name.
        """

        # Return the stored FHIR resource name
        return self._fhir_resource_name  



    @property
    def full_table_name(self):
        """     
        Read-only property to access the full table name.

        This property provides access to the full table name without allowing direct modification.
        The value is set during object initialization and retrieved when accessed.

        Returns:
        - str: The full table name in the format "project.dataset.table_name".
        """
        return self._full_table_name
    

    @log_entry_exit  
    def _extract_fhir_resource_name(self, full_table_name: str) -> str:
        """
        Extracts and converts a BigQuery table name into a FHIR resource name.

        This method ensures the input follows the correct format for a fully qualified BigQuery table 
        name (i.e., it contains at least two periods). If the format is invalid, an exception is raised.

        Steps:
        1. Validate that the input contains at least two periods (e.g., "project.dataset.table_name").
        2. Extract the last segment of the table name after the final period.
        3. If the extracted name starts with "fhir_", remove the prefix.
        4. Log the extracted resource name and return it.

        Parameters:
        - full_table_name (str): The fully qualified BigQuery table name in the format 
        "project.dataset.table_name".

        Returns:
        - str: The cleaned FHIR resource name (i.e., table name without "fhir_" prefix).

        Raises:
        - ValueError: If the input does not contain at least two periods, indicating an invalid format.
        """

        logger.info(f"Extracting FHIR resource name from table name: {full_table_name}")

        # Validate input format: Ensure it contains at least two periods
        if full_table_name.count(".") < 2:
            error_message = "Invalid table name format. Expected 'project.dataset.table_name'."
            logger.error(error_message)
            raise ValueError(error_message)

        # Extract the last part of the table name and clean it by removing "fhir_" prefix if present
        resource_name = full_table_name.split(".")[-1].replace("fhir_", "")
        
        logger.info(f"Extracted FHIR resource name: {resource_name}")

        return resource_name



    @log_entry_exit  # Decorator for logging function entry and exit
    def generate_table_description(self):
        """ 
        Generates a description for a FHIR resource name using an LLM. 
        This description is at the resource (or table) level, so it
        describes the resource as a whole.

        This method constructs a prompt dynamically using a stored prompt template and 
        then invokes the LLM model to generate a description of the given FHIR resource.

        Steps:
        1. Ensure the LLM model is initialized; otherwise, return a fallback message.
        2. Retrieve the appropriate prompt template from the database using its name.
        3. Set up a `PromptTemplate` to format the retrieved prompt.
        4. Inject the `fhir_resource_name` into the prompt and construct a message array.
        5. Invoke the LLM model to generate a description.
        6. Log the successful generation and return the description.
        7. Handle any errors gracefully and log them.

        Returns:
        - str: The generated description for the FHIR resource.
        If the LLM model is not available, returns `"No description available."`
        If an error occurs, logs the error and returns `None`.
        """

        # Ensure the LLM model is initialized; otherwise, return a fallback message
        if not self.llm_model:
            return "No description available."  # Fallback

        try:
            # Retrieve the prompt template from the database
            prompt_name = prompt_names.GET_TABLE_DESCRIPTION
            prompt_template_str = read_prompt_template(prompt_name)

            # Set up the prompt template with the expected input variable
            prompt_template = PromptTemplate(
                input_variables=["table_name", "description_length"],
                template=prompt_template_str
            )

            # Format the prompt by injecting the FHIR resource name
            prompt = prompt_template.format(
                            table_name=self.fhir_resource_name, 
                            description_length=CHARACTER_LIMIT) 

            # Create a message array containing the formatted prompt
            messages = [HumanMessage(content=prompt)]

            # Invoke the LLM model to generate a description
            description = self.llm_model.invoke(input=messages).content

            # Log successful retrieval of the description
            logger.info(f"Generated description for FHIR resource '{self._fhir_resource_name}' successfully retrieved.")

            return description

        except Exception as e:
            # Log the error and return None in case of failure
            logger.error(f"Error generating description for FHIR resource '{self._fhir_resource_name}': {e}")
            return None

    #============================================================================================================


    def count_tokens(self, text: str, model="gpt-4") -> int:
        """
        Counts the number of tokens in the given text.

        Parameters:
            text (str): The input text.
            model (str): The LLM model being used.

        Returns:
            int: Token count of the input text.
        """
        tokenizer = tiktoken.encoding_for_model(model)
        return len(tokenizer.encode(text))




    # def semantic_chunking(self, data: List[Dict], chunk_size: int = CHUNK_SIZE) -> List[List[Dict]]:
    #     """
    #     Chunks the JSON data into smaller batches of related records.
    #     """
    #     return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
    

    def semantic_chunking(self, data, chunk_size=10):
        """
        Chunking that ensures fields, especially nested RECORD types, are not split across chunks.
        """
        chunks = []
        current_chunk = []
        current_size = 0

        for record in data:
            # Check if adding this record would exceed chunk size
            if current_size + 1 > chunk_size:
                chunks.append(current_chunk)
                current_chunk = []
                current_size = 0

            # Add the entire RECORD field if it's nested, to prevent cutting off
            if record.get('type', '').lower() == 'record':
                current_chunk.append(record)
            else:
                current_chunk.append(record)
            
            current_size += 1

        if current_chunk:  # Append any remaining records
            chunks.append(current_chunk)

        return chunks



    



    # Function to process a chunk (you can replace this with LLM processing)
    @log_entry_exit
    def process_chunk(self, chunk: List[Dict]):
        """
        Processes each chunk of data. Here, it's a placeholder for LLM integration.
        """
        # We use the JSON Output Parser to extract the JSON array from the response
        # Using this parser, we get very predictable results, and we do not have
        # to worry about the structure of the response and extra "bits" emitted
        # by the LLM model
        parser = JsonOutputParser()
        instructions = parser.get_format_instructions()

        # Retrieve the appropriate prompt template from our prompt database
        prompt_name = prompt_names.GENERATE_RESOURCE_SCHEMA_DESCRIPTIONS
        prompt_template_str = read_prompt_template(prompt_name, "prompts")

        # Set up the prompt template with the expected input variables                  
        prompt_template = PromptTemplate(
            input_variables=["input_json_schema", "fhir_resource", "character_length"],
            template=prompt_template_str)

        # Format the prompt with the chunk
        prompt = prompt_template.format(
                        fhir_resource=self.fhir_resource_name, 
                        character_length = CHARACTER_LIMIT,
                        input_json_schema=json.dumps(chunk, indent=2))
        logger.info(f"Prepared the prompt...")

        # Measure prompt size in tokens
        token_count = self.count_tokens(prompt)
        logger.info(f"Prompt size: {token_count} tokens before sending to LLM.")

        # Create a message array containing the formatted prompt
        messages = [HumanMessage(content=prompt)]
        
        # Send request to LLM
        logger.info(f"Invoking the LLM model...")
        if self.llm_model is None:
            logger.error(f"LLM model not found.")
            return None
        response = self.llm_model.invoke(input=messages).content
        logger.info(f"LLM invocation completed successfully...")


        enriched_chunk = ""
        # Parse response and extend enriched schema
        try:
            # Use the JSsonOutputParser to extract the JSON array from the response,
            # and add it to the enriched schema
            logger.info("Invoking JsonOutputParser to parse the response...")
            enriched_chunk = parser.parse(response)

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON for chunk, error:{e}")

        bennie_chunk = {
            "bennie": enriched_chunk
        }

        retval =  json.dumps(bennie_chunk, indent=2)

        return retval




    @log_entry_exit
    def generate_enriched_schema_with_semantic_chunking(self, json_schema):
        logger.info(f"Generating enriched schema for FHIR resource: {self._fhir_resource_name}")

        combined_results = []

        try:
            # Since we cannot retrieve the context window sie from the LLM model, we will use a 
            # fixed size here
            context_window_size = 8192
            logger.info(f"Assuming a context window size of {context_window_size} tokens...")

            # Count the number of tokens in the document
            document_length_in_tokens = self.count_tokens(json.dumps(json_schema))
            logger.info(f"Document length in tokens: {document_length_in_tokens}")
            
            # Split the data into semantic chunks
            chunks = self.semantic_chunking(json_schema, chunk_size=CHUNK_SIZE)
            logger.info(f"Splitting schema into a total of {len(chunks)} chunks...")

            # Process chunks in parallel and handle exceptions per future
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_chunk = {executor.submit(self.process_chunk, chunk): chunk for chunk in chunks}

                for future in as_completed(future_to_chunk):
                    try:
                        result = future.result()
                        if result:
                            logger.info(f"Chunk processed successfully.")
                            parsed_result = json.loads(result)
                            combined_results.extend(parsed_result.get("bennie", []))  # Combine 'bennie' arrays
                        else:
                            logger.warning(f"Empty result returned for chunk.")
                    except Exception as e:
                        logger.error(f"Exception occurred while processing chunk: {e}")

            if combined_results:
                return combined_results
            else:
                logger.warning("No results were returned from processing chunks.")
                print("No results were returned.")

        except Exception as e:
            logger.error(f"Error generating schema with description for FHIR resource: {self._fhir_resource_name}: {e}")
            print(f"Exception in main function: {e}")

    #============================================================================================================

    @log_entry_exit  
    def generate_enriched_schema(self, json_schema):
        """
        This methoid generates an enriched schema by adding column-level 
        descriptionss for a given FHIR resource.

        Args:
        - json_schema (dict): The JSON schema for the FHIR resource.

        Returns:
        - list: The enriched schema with the column descriptions.
        """

        # We use the JSON Output Parser to extract the JSON array from the response
        # Using this parser, we get very predictable results, and we do not have
        # to worry about the structure of the response and extra "bits" emitted
        # by the LLM model
        parser = JsonOutputParser()
        instructions = parser.get_format_instructions()

        logger.info(f"Generating enriched schema for fhir resource: {self._fhir_resource_name}")

        try:
            # Define chunk size (e.g., process 10 fields at a time)
            # Because of the potentially large size of the models, we decided to 
            # use chunking here. This is a common practice when working with large
            # models and large amounts of data. We can adjust the chunk size as needed, 
            # but 10 is a good starting point.
            chunk_size = 10
            logger.info(f"Splitting schema into chunks of {chunk_size} fields...")
            schema_chunks = [json_schema[i:i + chunk_size] for i in range(0, len(json_schema), chunk_size)]
    

            # Retrieve the appropriate prompt template from our prompt database
            prompt_name = prompt_names.GENERATE_RESOURCE_SCHEMA_DESCRIPTIONS
            prompt_template_str = read_prompt_template(prompt_name, "prompts")

            # Set up the prompt template with the expected input variables                  
            prompt_template = PromptTemplate(
                input_variables=["input_json_schema", "fhir_resource", "character_length"],
                template=prompt_template_str)

            # Process each chunk
            enriched_schema = []
            for idx, chunk in enumerate(schema_chunks):
                logger.info(f"Processing chunk {idx + 1}/{len(schema_chunks)}...")

                # Format the prompt with the chunk
                prompt = prompt_template.format(
                                fhir_resource=self.fhir_resource_name, 
                                character_length = CHARACTER_LIMIT,
                                input_json_schema=json.dumps(chunk, indent=2))

                # Create a message array containing the formatted prompt
                messages = [HumanMessage(content=prompt)]
                
                # Send request to LLM
                response = self.llm_model.invoke(input=messages).content

                # Parse response and extend enriched schema
                try:
                    # Use the JSsonOutputParser to extract the JSON array from the response,
                    # and add it to the enriched schema
                    enriched_chunk = parser.parse(response)
                    enriched_schema.extend(enriched_chunk)

                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON for chunk {idx + 1}. error:{e}")

            logger.info("Creation of enriched schema completed successfully...")
            return enriched_schema
            
        except Exception as e:
            logger.error(f"Error generating schema with description for fhir resource: {self._fhir_resource_name}': {e}")



    def escape_description(self, desc: str) -> str:
        """
        Escapes special characters in descriptions for BigQuery SQL.
        
        Args:
            desc: The description text to escape
            
        Returns:
            Escaped string safe for BigQuery description options
        """
        return (
            desc.replace("\\", "\\\\")   # Escape backslashes
                .replace("'", "\\'")     # Escape single quotes
                .replace("\"", "\\\"")   # Escape double quotes
        )



    def build_struct_fields(self, fields: list) -> str:
        """
        Creates the inner content of a STRUCT definition from a list of fields.
        
        Args:
            fields (list): List of field definitions to process
            
        Returns:
            str: Comma-separated string of field definitions
        """
        # Process each subfield recursively
        subfield_sql_parts = []
        for subfield in fields:
            # Generate SQL for each subfield, including field name
            subfield_sql = self.get_field_sql(subfield, include_name=True)
            subfield_sql_parts.append(subfield_sql)
        
        # Join all parts with commas
        return ", ".join(subfield_sql_parts)



    def get_field_sql(self, field: dict, include_name: bool) -> str:
        """
        Recursively generates BigQuery column/subfield definition.
        
        Handles:
        - Nested STRUCT fields via recursion
        - REPEATED mode (ARRAY<...>)
        - Description attachment via OPTIONS
        
        Parameters:
        - field: Dictionary containing field metadata
        - include_name: Whether to prepend the field name
        
        Returns:
        A valid BigQuery DDL snippet for the field
        """
        # Extract field metadata with defaults
        name = field.get("name", "")
        field_type = field.get("type", "").upper()
        mode = field.get("mode", "NULLABLE").upper()
        description = field.get("description", "")

        # 1) Build base type: STRUCT<...> or scalar type
        if field_type in ("RECORD", "STRUCT"):
            # Handle nested fields 
            nested_fields = field.get("fields", [])
            struct_inner = self.build_struct_fields(nested_fields)
            base_type = f"STRUCT<{struct_inner}>"
        else:
            # Default to STRING if type is missing
            base_type = field_type if field_type else "STRING"

        # 2) Wrap in ARRAY if mode is REPEATED
        if mode == "REPEATED":
            base_type = f"ARRAY<{base_type}>"

        # 3) Conditionally add field name
        definition = f"{name} {base_type}" if include_name else base_type

        # 4) Add description if available
        if description:
            escaped_desc = self.escape_description(description)
            definition += f" OPTIONS(description='{escaped_desc}')"

        return definition


        
    def filter_empty_structs(self, schema: list) -> list:
        """
        Recursively remove any RECORD fields that have no subfields.
        This is necessary because BigQuery does not allow empty STRUCTs.
        
        Args:
            schema (list): The input schema to filter.
        
        Returns:
            list: The filtered schema with empty structs removed.
        """
        filtered = []
        for field in schema:
            field_type = field.get("type", "").upper()
            
            # Check if the field is a nested structure (RECORD or STRUCT)
            if field_type in ("RECORD", "STRUCT"):
                # Get the subfields, defaulting to an empty list
                subfields = field.get("fields", [])
                
                # Recursively filter the subfields first
                # This handles nested structs with potentially empty subfields
                subfields = self.filter_empty_structs(subfields)
                
                # If there are subfields after filtering, keep the field
                if subfields:
                    field["fields"] = subfields
                    filtered.append(field)
                else:
                    # If no subfields remain, skip this struct
                    print(f"Skipping empty struct field: {field['name']}")
            else:
                # For non-struct fields, keep them as-is
                filtered.append(field)
        
        return filtered



    @log_entry_exit
    def generate_create_table_sql(self, schema: list, table_description: str = "") -> str:
        """
        Generates a CREATE OR REPLACE TABLE SQL statement for BigQuery using the provided schema.
        Also sets table-level description.

        Parameters
        ----------
        full_table_name : str
            The fully-qualified table name, e.g. "project.dataset.table"
        schema : list
            A list of field dictionaries (the JSON schema).
        table_description : str
            Description for the table itself.

        Returns
        -------
        str
            The complete CREATE OR REPLACE TABLE statement.
        """
        # Build a comma-separated list of column definitions
        fields_sql = ",\n  ".join(self.get_field_sql(field, include_name=True) for field in schema)

        # Generate CREATE TABLE statement
        create_stmt = f"CREATE OR REPLACE TABLE `{self.full_table_name}` (\n  {fields_sql}\n)"

        # Optionally add the table-level description
        if table_description:
            escaped_table_desc = self.escape_description(table_description)
            create_stmt += f"\nOPTIONS(description=\"{escaped_table_desc}\");"
        else:
            create_stmt += ";"

        return create_stmt



    @log_entry_exit
    def generate_alter_table_sql(self, schema, table_description=""):
        """
        Generates up to TWO BigQuery ALTER TABLE statements:

        1) Table-level description (if provided):
                ALTER TABLE `project.dataset.table`
                SET OPTIONS(description="...");
            
            Ends with a semicolon (no trailing comma).

        2) A single statement for any top-level columns that need new descriptions:
                ALTER TABLE `project.dataset.table`
                ALTER COLUMN col1 SET OPTIONS(description="..."),
                ALTER COLUMN col2 SET OPTIONS(description="...");
            
            Each column update ends with a comma except the last one, 
            and then the statement ends with a semicolon.

        BigQuery does not allow altering nested (RECORD/STRUCT) fields, so we skip them.
        
        Returns:
            str
                One or two ALTER TABLE statements, each ending with a semicolon, 
                separated by a newline if both exist.
        """
        statements = []

        # ----- 1) Table-level description as its own statement -----
        if table_description:
            escaped_table_desc = (
                table_description
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
            )
            # Single statement, ends with semicolon, no trailing commas
            stmt_table_desc = (
                f'ALTER TABLE `{self.full_table_name}`\n'
                f'  SET OPTIONS(description="{escaped_table_desc}");'
            )
            statements.append(stmt_table_desc)

        # ----- 2) Gather column-level statements in a single ALTER TABLE -----
        column_ops = []
        for field in schema:
            name = field.get("name", "")
            if not name:
                continue

            field_type = (field.get("type") or "").upper()
            description = field.get("description", "")

            # Skip nested fields (RECORD/STRUCT)
            if field_type in ("RECORD", "STRUCT"):
                continue

            # If there's a description for a top-level column, prepare a sub-clause
            if description:
                escaped_desc = (
                    description
                    .replace("\\", "\\\\")
                    .replace("\"", "\\\"")
                )
                column_ops.append(
                    f'ALTER COLUMN {name} SET OPTIONS (description="{escaped_desc}")'
                )

        # Only generate the second statement if we have any column_ops
        if column_ops:
            # Join column_ops with commas, and the final entry ends the line (no trailing comma)
            if len(column_ops) == 1:
                # Just one column => no comma needed
                clauses_str = column_ops[0]
            else:
                # Multiple columns => separate sub-clauses with commas
                # Each clause is on its own line
                clauses_str = ",\n  ".join(column_ops)

            stmt_column_desc = (
                f'ALTER TABLE `{self.full_table_name}`\n'
                f'  {clauses_str};'
            )
            statements.append(stmt_column_desc)

        # Join both statements (if present) with a newline
        return "\n".join(statements)






    @log_entry_exit
    def generate_sql(self, json_schema, table_description, mode):
        """
        Generates a CREATE TABLE or ALTER TABLE SQL statement based on the 
        provided schema and the passed-in mode

        args:
            - json_schema (dict): The JSON schema for the FHIR resource.
            - table_description (str): The description for the table.
            - mode (str): The mode to use, either "create" or "alter".

        returns:
            - str: The generated SQL statement. 
        """

        # First, we clean the schema by removing any empty structs, 
        # which are not allowed in BigQuery
        cleaned_schema = self.filter_empty_structs(json_schema)

        # Check the mode, and generate the appropriate SQL
        if mode == "alter":
            return self.generate_alter_table_sql(cleaned_schema, table_description)
        

        elif mode == "create":
            return self.generate_create_table_sql(cleaned_schema, table_description)

        else:
            raise ValueError(f"Invalid mode specified: {mode}")
        
    
    