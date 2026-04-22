"""
数据集处理工具模块
用于模型闭环迭代中的数据集混合、增强与配置生成。
"""
import os
import glob
import yaml
import shutil
from pathlib import Path

def prepare_finetune_dataset(
    orig_yaml_path: str, 
    verified_dir: str, 
    output_dir: str = "finetune_dataset",
    repeat_count: int = 5
) -> str:
    """
    准备微调数据集：混合原始数据 + 加权的新增数据
    
    Args:
        orig_yaml_path: 原始 data.yaml 路径
        verified_dir: 已复核的新数据目录 (需包含 images 和 labels 子目录)
        output_dir: 输出目录
        repeat_count: 新数据重复次数 (加权)
        
    Returns:
        str: 新生成的 data_finetune.yaml 绝对路径
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 读取原始配置
    with open(orig_yaml_path, 'r', encoding='utf-8') as f:
        data_config = yaml.safe_load(f)
        
    # 获取原始训练集路径 (可能是字符串或列表)
    # 注意：YOLO yaml 中的 path 可能是相对于 yaml 文件的，也可能是绝对路径
    base_path = data_config.get('path', os.path.dirname(orig_yaml_path))
    train_images_orig = data_config.get('train')
    
    if not isinstance(train_images_orig, list):
        train_images_orig = [train_images_orig]
        
    # 解析原始图片列表
    orig_img_paths = []
    for p in train_images_orig:
        full_p = p if os.path.isabs(p) else os.path.join(base_path, p)
        # 如果是目录，扫描；如果是文件(txt)，读取
        if os.path.isdir(full_p):
            # 简单扫描常见图片格式
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
                orig_img_paths.extend(glob.glob(os.path.join(full_p, ext)))
                orig_img_paths.extend(glob.glob(os.path.join(full_p, "**", ext), recursive=True))
        elif os.path.isfile(full_p) and full_p.endswith('.txt'):
            with open(full_p, 'r') as f:
                lines = f.read().splitlines()
                # 处理相对路径
                txt_dir = os.path.dirname(full_p)
                orig_img_paths.extend([l if os.path.isabs(l) else os.path.join(txt_dir, l) for l in lines])
                
    # 2. 扫描新数据
    verified_images_dir = os.path.join(verified_dir, "images")
    new_img_paths = []
    if os.path.exists(verified_images_dir):
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
            new_img_paths.extend(glob.glob(os.path.join(verified_images_dir, ext)))
            
    if not new_img_paths:
        print("警告：未在 verified_dataset 中发现新图片")
        
    # 3. 生成混合列表 (加权策略：新数据重复 N 次)
    final_train_list = orig_img_paths.copy()
    
    # Physical Oversampling
    for _ in range(max(1, repeat_count)):
        final_train_list.extend(new_img_paths)
        
    # 4. 写入 txt 文件
    train_txt_path = os.path.abspath(os.path.join(output_dir, "train_finetune.txt"))
    with open(train_txt_path, 'w', encoding='utf-8') as f:
        for p in final_train_list:
            f.write(os.path.abspath(p) + "\n")
            
    # 验证集保持不变 (或也加入一部分新数据，这里暂且复用原始验证集)
    # val_path 保持原样
    
    # 5. 生成新的 yaml
    new_config = data_config.copy()
    new_config['path'] = os.path.abspath(output_dir) # 设置新的根路径
    new_config['train'] = train_txt_path
    
    # 如果 val 是相对路径，尝试转为绝对路径以免在新位置失效
    val_orig = new_config.get('val')
    if val_orig and not os.path.isabs(val_orig):
        # 假设原 val 相对于原 yaml
        val_abs = os.path.abspath(os.path.join(base_path, val_orig))
        if os.path.exists(val_abs):
            new_config['val'] = val_abs
            
    new_yaml_path = os.path.join(output_dir, "data_finetune.yaml")
    with open(new_yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(new_config, f, allow_unicode=True)
        
    return new_yaml_path
