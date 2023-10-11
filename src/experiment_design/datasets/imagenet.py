import pathlib
from PIL import Image

from dataset import BaseDataset
import torchvision.transforms as transforms


class ImagenetDataset(BaseDataset):
    """
    Here's an example of a 'user-defined' dataset class extending the included BaseDataset
    class. Below the class definitions are some instances of this class that can later be 
    referenced by participating nodes for experiments.
    """

    CLASS_TEXTFILE: pathlib.Path
    IMG_DIRECTORY: pathlib.Path

    def __init__(self,
                 max_iter: int = -1,
                 transform=None,
                 target_transform=None
                 ):
        self.CLASS_TEXTFILE = self.DATA_SOURCE_DIRECTORY / "imagenet" / "imagenet_classes.txt"
        self.IMG_DIRECTORY = self.DATA_SOURCE_DIRECTORY / "imagenet" / "sample_images"

        with open(self.CLASS_TEXTFILE, 'r') as file:
            img_labels = "\n".split(file.read())
        if len(img_labels) > max_iter > 0:
            img_labels = img_labels[:max_iter]

        self.img_labels = img_labels
        self.img_dir = self.IMG_DIRECTORY
        self.transform = transform
        self.target_transform = target_transform
        self.img_map = {img_class: next(self.img_dir.glob(f"*{img_class}*"))
            for img_class in self.img_labels}

    def __len__(self):
        return len(self.img_labels)

    def __getitem__(self, idx):
        label = self.img_labels[idx]
        img_fp = self.img_map[label]
        image = Image.open(img_fp).convert("RGB")

        if self.transform:
            image = self.transform(image)
        if self.target_transform:
            label = self.target_transform(label)

        return image, label

# Here are the dataset instances the observer can offer to the participants

# All 999 images as PIL objects converted to RGB
imagenet999_rgb = ImagenetDataset()
# Same, but just the first 10 
imagenet10_rgb = ImagenetDataset(max_iter=10)

# This gives all 999 images as torch Tensors
imagenet999_tr = ImagenetDataset(transform=transforms.ToTensor)
# And this gives the same, but only the first 10 
imagenet10_tr = ImagenetDataset(transform=transforms.ToTensor, max_iter=10)
