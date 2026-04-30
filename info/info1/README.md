# Mapping Script

## 数据来源

- `humanml.zip`文件夹中的内容来源于[Hugging Face](https://huggingface.co/datasets/USC-GVL/Humanoid-X/tree/main)上的`texts.zip`。请确保在使用前解压`texts.zip`，并将其内容放置在`humanml`目录中。

## 功能

- **视频文件名到索引的映射**：从 CSV 文件中读取视频信息，并生成视频文件名到索引的映射。
- **动词提取**：从文本描述文件中提取动词，并统计其出现频率。
- **描述文件检查**：检查每个视频是否都有对应的文本描述文件。
- **数据保存**：将生成的映射字典保存为 JSON 文件。

## 使用方法

### 命令行参数

- `--humanml3d_csv_path`：指定包含视频信息的 CSV 文件路径。
- `--txt_dscpt_fdpath`：指定包含文本描述文件的目录路径。
- `--prefix_to_add`：指定要添加到视频文件名前缀的字符串。
- `--output_dir`：指定保存 JSON 文件的目录。

### 示例
```bash
python mapping.py --humanml3d_csv_path ./index.csv --txt_dscpt_fdpath ./humanml --prefix_to_add "0-" --output_dir "stat"
```

## 输出

- `videofn2idx.json`：视频文件名到索引的映射。
- `idx2videofn.json`：索引到视频文件名的映射。
- `verb_dict.json`：动词及其频率和相关信息。
- `idx2verb.json`：文件索引到动词的映射。
- `videofn_info.json`：每个视频的详细信息，包括动词和句子。

## 注意事项

- **执行前解压所有压缩包**
- 确保所有输入路径和文件格式正确。
- 如果输出目录中已存在同名 JSON 文件，脚本将覆盖这些文件。
