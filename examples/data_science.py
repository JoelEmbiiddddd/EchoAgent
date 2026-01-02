from workflows.data_scientist import DataScientistWorkflow, DataScienceQuery

# Load the default configuration file and start the workflow using the one-parameter API.
pipe = DataScientistWorkflow("workflows/configs/data_science.yaml")

query = DataScienceQuery(
    prompt="Analyze the dataset and build a predictive model",
    data_path="data/banana_quality.csv"
)

pipe.run_sync(query)
