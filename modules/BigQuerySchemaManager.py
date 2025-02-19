import json
from google.cloud import bigquery

class BigQuerySchemaManager:
    def __init__(self, bq_project_id, location='us'):
        self.client = bigquery.Client(project=bq_project_id, location=location)
        #self.dataset_id = dataset_id

    def get_table_schema(self, table_name, format="DDL"):
        table_ref = table_name # f"{self.client.project}.{self.dataset_id}.{table_name}"
        table = self.client.get_table(table_ref)
        
        if format.upper() == "DDL":
            return self._generate_create_table_ddl(table)

        elif format.upper() == "JSON":
            return json.dumps([field.to_api_repr() for field in table.schema], indent=2)
        
        else:
            raise ValueError("Invalid format. Choose 'DDL' or 'JSON'.")

    def _generate_create_table_ddl(self, table):
        """ Recursively generates the CREATE TABLE DDL for deeply nested schemas, including arrays. """
        ddl = f"CREATE TABLE `{table.project}.{table.dataset_id}.{table.table_id}` (\n"
        ddl += self._process_schema_fields(table.schema, indent=2)
        ddl += "\n);"
        return ddl

    def _process_schema_fields(self, fields, indent=2):
        """ Recursively processes fields, including nested STRUCT and ARRAY types. """
        sql_lines = []

        for field in fields:
            field_name = field.name
            field_type = field.field_type.upper()
            is_repeated = field.mode == "REPEATED"
            
            # Handle nested STRUCT (RECORD) fields
            if field_type == "RECORD" and field.fields:
                nested_fields = self._process_schema_fields(field.fields, indent + 2)
                struct_definition = f"STRUCT<\n{nested_fields}\n{' ' * indent}>"
                
                # If the field is REPEATED, wrap it inside an ARRAY<>
                if is_repeated:
                    sql_lines.append(f"{' ' * indent}{field_name} ARRAY<{struct_definition}>")
                else:
                    sql_lines.append(f"{' ' * indent}{field_name} {struct_definition}")
            
            else:
                # Handle primitive types
                if is_repeated:
                    sql_lines.append(f"{' ' * indent}{field_name} ARRAY<{field_type}>")
                else:
                    sql_lines.append(f"{' ' * indent}{field_name} {field_type}")

        return ",\n".join(sql_lines)
