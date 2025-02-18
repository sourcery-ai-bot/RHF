import os
import time
import json

import torch
import torchvision
from PIL import Image
import matplotlib.pyplot as plt

from torchvision import transforms
from network_files import FasterRCNN, FastRCNNPredictor, AnchorsGenerator
from backbone_hdc import resnet50_fpn_backbone, MobileNetV2
from draw_box_utils import draw_box


def create_model(num_classes):
    # mobileNetv2+faster_RCNN
    # backbone = MobileNetV2().features
    # backbone.out_channels = 1280
    #
    # anchor_generator = AnchorsGenerator(sizes=((32, 64, 128, 256, 512),),
    #                                     aspect_ratios=((0.5, 1.0, 2.0),))
    #
    # roi_pooler = torchvision.ops.MultiScaleRoIAlign(featmap_names=['0'],
    #                                                 output_size=[7, 7],
    #                                                 sampling_ratio=2)
    #
    # model = FasterRCNN(backbone=backbone,
    #                    num_classes=num_classes,
    #                    rpn_anchor_generator=anchor_generator,
    #                    box_roi_pool=roi_pooler)

    # resNet50+fpn+faster_RCNN
    # 注意，这里的norm_layer要和训练脚本中保持一致
    backbone = resnet50_fpn_backbone(norm_layer=torch.nn.BatchNorm2d)
    return FasterRCNN(
        backbone=backbone, num_classes=num_classes, rpn_score_thresh=0.5
    )


def time_synchronized():
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    return time.time()


def main():
    # get devices
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"using {device} device.")

    # create model
    model = create_model(num_classes=4)

    # load train weights
    train_weights = r"save_weights\resNetHDCFpn-model-Augment-TrainSecond-19.pth"
    # train_weights = r"./save_weights/resNetHDCFpn-model-NotAugment-19.pth"
    # train_weights = "./save_weights/resNetHDCFpn-model-NotAugment-19.pth"
    assert os.path.exists(train_weights), f"{train_weights} file dose not exist."
    model.load_state_dict(torch.load(train_weights, map_location=device)["model"])
    model.to(device)

    # read class_indict
    label_json_path = './classes.json'
    assert os.path.exists(
        label_json_path
    ), f"json file {label_json_path} dose not exist."
    with open(label_json_path, 'r') as json_file:
        class_dict = json.load(json_file)
    category_index = {v: k for k, v in class_dict.items()}

    # load image
    original_img = Image.open("test_images/test1.jpg")

    # from pil image to tensor, do not normalize image
    data_transform = transforms.Compose([transforms.ToTensor()])
    img = data_transform(original_img)
    # expand batch dimension
    img = torch.unsqueeze(img, dim=0)

    model.eval()  # 进入验证模式
    with torch.no_grad():
        # init
        img_height, img_width = img.shape[-2:]
        init_img = torch.zeros((1, 3, img_height, img_width), device=device)
        model(init_img)

        t_start = time_synchronized()
        predictions = model(img.to(device))[0]
        t_end = time_synchronized()
        print(f"inference+NMS time: {t_end - t_start}")

        predict_boxes = predictions["boxes"].to("cpu").numpy()
        predict_classes = predictions["labels"].to("cpu").numpy()
        predict_scores = predictions["scores"].to("cpu").numpy()

        if len(predict_boxes) == 0:
            print("没有检测到任何目标!")

        draw_box(original_img,
                 predict_boxes,
                 predict_classes,
                 predict_scores,
                 category_index,
                 thresh=0.6,
                 line_thickness=3)
        plt.imshow(original_img)
        plt.show()
        # 保存预测的图片结果
        original_img.save("test_images/test1_result_ResNet50HDC_Augment.jpg")


if __name__ == '__main__':
    main()

