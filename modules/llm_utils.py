from langchain.prompts import PromptTemplate
from langchain_openai.chat_models import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.output_parsers import PydanticOutputParser

# from modules.ColumnInfo import ColumnInfo
from logger_setup import logger, log_entry_exit


# Function to initialize the LangChain LLM (Language Learning Model)
@log_entry_exit  # Decorator for logging function entry and exit
def get_llm(model_name):
    """
    Initializes and returns an appropriate LangChain LLM model based on the provided model name.
    
    Parameters:
    - model_name (str): The name of the LLM model to be used.
    
    Returns:
    - An instance of either ChatGoogleGenerativeAI or ChatOpenAI, depending on the model name.
    
    Behavior:
    - If the model name contains "gemini" (case-insensitive), it initializes a Google Gemini model.
    - Otherwise, it defaults to an OpenAI Chat model.
    - Both models are initialized with:
      - `temperature=0.0` (ensuring deterministic output)
      - `max_tokens=15000` (limiting response length)
    """

    # Check if the model name contains "gemini" (case insensitive)
    if "gemini" in model_name.lower():
        
        # Initialize Google Gemini LLM
        logger.info(f"Using Google Generative AI model: {model_name}")
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.0) 

        if llm is None:
            raise ValueError(f"Google Generative AI model '{model_name}' not found.")
        return ChatGoogleGenerativeAI(model=model_name, temperature=0.0)
    else:
    
        # Default to OpenAI Chat model
        logger.info(f"Using OpenAI Chat model: {model_name}")
        return ChatOpenAI(model=model_name, temperature=0.0)



# # Initialize the LangChain LLM
# llm = ChatOpenAI(
#     model="gpt-4o",  # Use GPT-4 or another supported model
#     temperature=0.0,
#     max_tokens=1000
# )

# # Initialize the output parser
# output_parser = PydanticOutputParser(pydantic_object=ColumnInfo)

# # Prompt template for table descriptions
# table_prompt = PromptTemplate(
#     input_variables=["table_name"],
#     template=(
#         "You are a database administrator with a strong medical background. "
#         "Provide a brief description of a database table:\n"
#         "Table Name: {table_name}\n"
#         "Context: This table is part of a relational database schema."
#     )
# )

# # Prompt template for column descriptions
# column_prompt = PromptTemplate(
#     input_variables=["table_name", "column_name", "data_type", "valid_data_types"],
#     template=(
#         "You are a database administrator with a strong medical background. "
#         "Your task is to provide the following details for a database column in JSON format:\n\n"
#         "1. A brief description of the column.\n"
#         "2. The mapped data type based on the provided valid data types.\n\n"
#         "Details:\n"
#         "- Column Name: {column_name}\n"
#         "- Table Name: {table_name}\n"
#         "- Native Data Type: {data_type}\n"
#         "- Valid Data Types: {valid_data_types}\n\n"
#         "Output your response in the following JSON format:\n"
#         "{format_instructions}"
#     ),
#     partial_variables={"format_instructions": output_parser.get_format_instructions()}
# )

# # LangChain chains
# table_chain = table_prompt | llm
# column_chain = column_prompt | llm | output_parser


# def generate_table_description(table_name: str) -> str:
#     """
#     Generate a description for a table using LangChain.
#     """
#     response = table_chain.invoke({"table_name": table_name})
#     return response.strip() if isinstance(response, str) else response.content


# def generate_column_description(
#     table_name: str, column_name: str, data_type: str, valid_data_types: list
# ) -> ColumnInfo:
#     """
#     Generate a description for a column using LangChain.
#     """
#     return column_chain.invoke({
#         "table_name": table_name,
#         "column_name": column_name,
#         "data_type": data_type,
#         "valid_data_types": ", ".join(valid_data_types)
#     })
