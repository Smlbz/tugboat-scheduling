import PyPDF2
import sys

def read_pdf(file_path):
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += f"\n\n=== 第{page_num + 1}页 ===\n\n"
                text += page.extract_text()
            return text
    except Exception as e:
        return f"读取文件出错: {str(e)}"

if __name__ == "__main__":
    files = [
        r"e:\船舶\高神舟版本.pdf",
        r"e:\船舶\李晨亮版本.pdf",
        r"e:\船舶\基于认知型多智能体的青岛港轮驳作业调度系统技术建设方案（V1.0）(1).pdf"
    ]
    
    for file_path in files:
        print(f"\n\n{'='*80}")
        print(f"文件: {file_path}")
        print('='*80)
        content = read_pdf(file_path)
        print(content)
        print("\n")
