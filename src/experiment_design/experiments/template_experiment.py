# src/experiment_design/experiments/template_experiment.py

import sys
from pathlib import Path
from typing import Dict, Any, Optional
import torch
import time
from tqdm import tqdm

# Add the project root to the Python path
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.experiment_design.models.model_hooked import WrappedModel
from src.utils.ml_utils import DataUtils  # Import appropriate utility classes
from src.interface.bridge import ExperimentInterface, ModelInterface
from src.experiment_design.datasets.dataloader import DataManager

class TemplateExperiment(ExperimentInterface):
    def __init__(self, config: Dict[str, Any], host: str, port: int):
        self.config = config
        self.host = host
        self.port = port
        self.model = self.initialize_model()
        self.data_utils = self.initialize_data_utils()
        self.data_loader = self.setup_dataloader()

    def initialize_model(self) -> ModelInterface:
        model = WrappedModel(config=self.config)
        model.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        model.eval()
        return model

    def initialize_data_utils(self):
        # Initialize any data utility classes you need
        return DataUtils()

    def setup_dataloader(self):
        dataset_config = self.config["dataset"][self.config["default"]["default_dataset"]]
        dataloader_config = self.config["dataloader"]
        dataset = DataManager.get_dataset({"dataset": dataset_config, "dataloader": dataloader_config})
        return torch.utils.data.DataLoader(
            dataset,
            batch_size=dataloader_config["batch_size"],
            shuffle=dataloader_config["shuffle"],
            num_workers=dataloader_config["num_workers"]
        )

    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        out, original_size = data['input']
        split_layer_index = data['split_layer']

        with torch.no_grad():
            if isinstance(out, dict):
                for key, value in out.items():
                    if isinstance(value, torch.Tensor):
                        out[key] = value.to(self.model.device)
            
            res = self.model(out, start=split_layer_index)
            # Process the results as needed for your specific experiment
            processed_results = self.data_utils.postprocess(res, original_size)

        return {'results': processed_results}

    def run(self):
        total_layers = self.config['model'][self.config['default']['default_model']]['total_layers']
        time_taken = []

        for split_layer_index in range(1, total_layers):
            host_time, travel_time, server_time, processing_time = self.test_split_performance(split_layer_index)
            print(f"Split at layer {split_layer_index}, Processing Time: {processing_time:.2f} seconds")
            time_taken.append((split_layer_index, host_time, travel_time, server_time, processing_time))

        best_split, host_time, travel_time, server_time, min_time = min(time_taken, key=lambda x: x[4])
        print(f"Best split at layer {best_split} with time {min_time:.2f} seconds")

        self.save_results(time_taken)

    def test_split_performance(self, split_layer_index: int):
        host_times, travel_times, server_times = [], [], []

        for input_tensor, _ in tqdm(self.data_loader, desc=f"Testing split at layer {split_layer_index}"):
            host_start_time = time.time()
            input_tensor = input_tensor.to(self.model.device)
            out = self.model(input_tensor, end=split_layer_index)
            host_end_time = time.time()
            host_times.append(host_end_time - host_start_time)

            # Simulate network transfer (replace with actual network transfer in a real setup)
            travel_start_time = time.time()
            time.sleep(0.01)
            travel_end_time = time.time()
            travel_times.append(travel_end_time - travel_start_time)

            server_start_time = time.time()
            _ = self.process_data({'input': (out, None), 'split_layer': split_layer_index})
            server_end_time = time.time()
            server_times.append(server_end_time - server_start_time)

        total_host_time = sum(host_times)
        total_travel_time = sum(travel_times)
        total_server_time = sum(server_times)
        total_processing_time = total_host_time + total_travel_time + total_server_time

        return total_host_time, total_travel_time, total_server_time, total_processing_time

    def save_results(self, results: Dict[str, Any]):
        import pandas as pd
        df = pd.DataFrame(results, columns=["Split Layer Index", "Host Time", "Travel Time", "Server Time", "Total Processing Time"])
        df.to_excel(f"{self.__class__.__name__}_split_layer_times.xlsx", index=False)
        print(f"Results saved to {self.__class__.__name__}_split_layer_times.xlsx")

    def load_data(self) -> Any:
        # Implement if needed for your experiment
        pass

    def setup_socket(self):
        # Implement if needed for your experiment
        pass

    def receive_data(self, conn: Any) -> Optional[Dict[str, Any]]:
        # Implement if needed for your experiment
        pass

    def send_result(self, conn: Any, result: Dict[str, Any]):
        # Implement if needed for your experiment
        pass