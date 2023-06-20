import sys
import logging
import os
import io
import grpc
import pandas as pd
import time
import re
import uuid
import pickle
import blosc2 as blosc
# import blosc
import numpy as np
from PIL import Image

from src.colab_vision import USE_COMPRESSION

sys.path.append(".")
parent = os.path.abspath('.')
sys.path.insert(1, parent)


from test_data import test_data_loader as data_loader
import alexnet_pytorch_split as alex

from . import colab_vision
from . import colab_vision_pb2
from . import colab_vision_pb2_grpc

client_mode = 'cpu'

class FileClient:
    def __init__(self, address):
        self.channel = grpc.insecure_channel(address)
        self.stub = colab_vision_pb2_grpc.colab_visionStub(self.channel)
        self.results_dict = {}
        logging.basicConfig()
        self.model = alex.Model(mode = client_mode)

    def safeClose(self):
        self.channel.close()
        df = pd.DataFrame(data = self.results_dict)
        df.to_csv('./test_results/test_results-12-18-cpu.csv')
        # for result, dic in self.results_dict.items():
        #     if 'client_complete_time' in dic.keys():
        #         print(f"{result}:\n\tOverall Time\t{dic['client_complete_time'] - dic['client_start_time']}")
        #     for key, val in dic.items():
        #         if re.search("^server.*time$", key):
        #             val += dic["server_reference_float"]
        #         if key != "server_reference_float": #lazy
        #             print(f"\t{key}\t{val}")
        
    def initiateInference(self, target):
        #stuff
        messages = self.stub.constantInference(self.inference_generator(target))
        for received_msg in messages:
            # print(f"Received message from server for id:{received_msg.id} ")
            self.results_dict[received_msg.id]["server_result_class"] = received_msg.results
            self.results_dict[received_msg.id]["client_complete_time"] = time.time()
            for key, val in received_msg.keypairs.items():
                # print(f"{key}, {val}")
                self.results_dict[received_msg.id][key] = val
            # self.results_dict[received_msg.id].pop("server_reference_float")

    def inference_generator_test(self, data_loader):
        for i in range(5):
            yield colab_vision_pb2.Info_Chunk(id = "test")

    def inference_generator(self, data_loader):
        # print("image available.")
        tmp = data_loader.next()
        while(tmp):
            size_packets = 0
            try:
                [ current_obj, exit_layer, filename ] = next(tmp)
            except StopIteration:
                return
            message = colab_vision_pb2.Info_Chunk()
            message.id = uuid.uuid4().hex # uuid4().bytes is utf8 not unicode like grpc wants
            message.layer = exit_layer # the server begins inference 1 layer above where the edge exited
            self.results_dict[message.id] = {} 
            self.results_dict[message.id]["filename"] = filename
            self.results_dict[message.id]["client_mode"] = client_mode
            self.results_dict[message.id]["split_layer"] = exit_layer
            self.results_dict[message.id]["compression_level"] = "9"
            self.results_dict[message.id]["client_start_time"] = time.time()
            # print(f"exit layer: {exit_layer}")
            current_obj = self.model.predict(current_obj, end_layer=exit_layer)
            self.results_dict[message.id]["client_predict_time"] = time.time()
            self.results_dict[message.id]["client_tensor_raw_bytes"] = 32 * np.prod(list(current_obj.size()))
            if colab_vision.USE_COMPRESSION:
                message.action.append(colab_vision_pb2.ACT_COMPRESSED)
                # Custom compression sizes require we provide tensor shape info to the server
                # current_obj = blosc.compress(current_obj.numpy().to_bytes(), clevel = 9) #force = True if we move to 1.13
                # current_obj = blosc.pack_tensor(current_obj)
                current_obj = blosc.pack_array(current_obj.cpu().numpy())
                self.results_dict[message.id]["client_compression_time"] = time.time()
            # send all pieces
            message.action.append(colab_vision_pb2.ACT_RESET)
            for i, piece in enumerate(colab_vision.get_object_chunks(current_obj)):
                message.chunk.chunk = piece
                # message.chunk.CopyFrom(piece)
                if i == 1:
                    message.action.remove(colab_vision_pb2.ACT_RESET)
                yield message # might be sending twice?
                size_packets += len(message.chunk.chunk)
            message.ClearField('chunk')
            message.chunk.chunk = b''
            # clear RESET from single msg inferences
            if(colab_vision_pb2.ACT_RESET in message.action):
                message.action.remove(colab_vision_pb2.ACT_RESET)
            message.action.append(colab_vision_pb2.ACT_INFERENCE)
            yield message # might be sending twice?
            self.results_dict[message.id]["client_upload_time"] = time.time()
            self.results_dict[message.id]["client_upload_bytes"] = size_packets


    # def start(self, port):
    #     self.server.add_insecure_port(f'[::]:{port}')
    #     self.server.start()
    #     self.server.wait_for_termination()