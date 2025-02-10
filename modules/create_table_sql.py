import json

# Function to map BigQuery types to SQL-compatible types
def map_bq_type(bq_type):
    type_mapping = {
        "STRING": "STRING",
        "BYTES": "BYTES",
        "INTEGER": "INT64",
        "FLOAT": "FLOAT64",
        "BOOLEAN": "BOOL",
        "TIMESTAMP": "TIMESTAMP",
        "DATE": "DATE",
        "TIME": "TIME",
        "DATETIME": "DATETIME",
        "GEOGRAPHY": "GEOGRAPHY",
        "NUMERIC": "NUMERIC",
        "BIGNUMERIC": "BIGNUMERIC"
    }
    return type_mapping.get(bq_type, bq_type)


import re

def escape_description(description):
    if description:
        description = description.replace('\xa0', ' ')  # Replace non-breaking spaces
        return re.sub(r'\s+', ' ', description).replace('"', '\\"').replace("'", "''").strip()
    return ""



# Recursive function to process schema fields
def process_fields(fields, indent=2):
    sql_lines = []
    
    for field in fields:
        field_name = field["name"]
        field_type = map_bq_type(field["type"])
        field_mode = field.get("mode", "NULLABLE")
        field_description = escape_description(field.get("description", ""))

        # Handle nested RECORD types
        if field_type == "RECORD" and "fields" in field:
            nested_fields = process_fields(field["fields"], indent + 2)
            sql_lines.append(f"{' ' * indent}{field_name} STRUCT<\n{nested_fields}\n{' ' * indent}>")
        else:
            nullable = "NOT NULL" if field_mode == "REQUIRED" else ""
            options_clause = f" OPTIONS(description=\"{field_description}\")" if field_description else ""
            sql_lines.append(f"{' ' * indent}{field_name} {field_type} {nullable}{options_clause}")
    
    return ",\n".join(sql_lines)

# Function to generate CREATE TABLE SQL statement
def generate_create_table_sql(schema_path, table_name):
    with open(schema_path, "r") as file:
        schema = json.load(file)

    sql_fields = process_fields(schema)
    create_table_sql = f"""
    CREATE OR REPLACE TABLE `{table_name}` (
{sql_fields}
    );
    """
    return create_table_sql.strip()
