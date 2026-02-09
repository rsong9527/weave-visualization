"""
vits-simple-api 接口调用示例

使用前请确保:
1. vits-simple-api 服务已启动 (默认 http://localhost:23456)
2. 已加载至少一个语音模型

使用方法:
    python api_examples.py
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error


BASE_URL = os.environ.get("VITS_API_URL", "http://localhost:23456")


def get_speakers():
    """获取已加载的所有说话人列表"""
    url = f"{BASE_URL}/voice/speakers"
    print(f"\n{'='*60}")
    print(f"[GET] {url}")
    print(f"{'='*60}")

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            print(json.dumps(data, indent=2, ensure_ascii=False))

            # 统计各模型类型的说话人数量
            total = 0
            for model_type, speakers in data.items():
                count = len(speakers)
                total += count
                if count > 0:
                    print(f"\n  [{model_type}] {count} 个说话人:")
                    for s in speakers[:5]:  # 最多显示5个
                        print(f"    - ID:{s.get('id', '?')} Name:{s.get('name', '?')} Lang:{s.get('lang', '?')}")
                    if count > 5:
                        print(f"    ... 还有 {count - 5} 个")

            if total == 0:
                print("\n  [警告] 没有加载任何模型！请将模型放入 data/models/ 目录")
            return data
    except urllib.error.URLError as e:
        print(f"  [错误] 无法连接到服务: {e}")
        print(f"  请确保 vits-simple-api 正在运行 ({BASE_URL})")
        return None


def get_default_parameters():
    """获取默认参数配置"""
    url = f"{BASE_URL}/voice/default_parameter"
    print(f"\n{'='*60}")
    print(f"[GET] {url}")
    print(f"{'='*60}")

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return data
    except urllib.error.URLError as e:
        print(f"  [错误] {e}")
        return None


def tts_vits(text, speaker_id=0, lang="auto", output_file="output_vits.wav"):
    """VITS 文本转语音"""
    params = urllib.parse.urlencode({
        "text": text,
        "id": speaker_id,
        "lang": lang,
        "format": "wav",
        "length": 1.0,
        "noise": 0.33,
        "noisew": 0.4,
        "segment_size": 50,
    })
    url = f"{BASE_URL}/voice/vits?{params}"
    print(f"\n{'='*60}")
    print(f"[VITS TTS] text='{text}' id={speaker_id} lang={lang}")
    print(f"[GET] {url}")
    print(f"{'='*60}")

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as response:
            audio_data = response.read()
            with open(output_file, "wb") as f:
                f.write(audio_data)
            size_kb = len(audio_data) / 1024
            print(f"  [成功] 已保存到 {output_file} ({size_kb:.1f} KB)")
            return output_file
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [错误] HTTP {e.code}: {body}")
        return None
    except urllib.error.URLError as e:
        print(f"  [错误] {e}")
        return None


def tts_bert_vits2(text, speaker_id=0, lang="auto", output_file="output_bert_vits2.wav"):
    """Bert-VITS2 文本转语音"""
    params = urllib.parse.urlencode({
        "text": text,
        "id": speaker_id,
        "lang": lang,
        "format": "wav",
        "length": 1.0,
        "noise": 0.33,
        "noisew": 0.4,
        "sdp_ratio": 0.2,
        "segment_size": 50,
    })
    url = f"{BASE_URL}/voice/bert-vits2?{params}"
    print(f"\n{'='*60}")
    print(f"[Bert-VITS2 TTS] text='{text}' id={speaker_id} lang={lang}")
    print(f"[GET] {url}")
    print(f"{'='*60}")

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as response:
            audio_data = response.read()
            with open(output_file, "wb") as f:
                f.write(audio_data)
            size_kb = len(audio_data) / 1024
            print(f"  [成功] 已保存到 {output_file} ({size_kb:.1f} KB)")
            return output_file
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [错误] HTTP {e.code}: {body}")
        return None
    except urllib.error.URLError as e:
        print(f"  [错误] {e}")
        return None


def tts_gpt_sovits(text, speaker_id=0, lang="auto", output_file="output_gpt_sovits.wav"):
    """GPT-SoVITS 文本转语音"""
    params = urllib.parse.urlencode({
        "text": text,
        "id": speaker_id,
        "lang": lang,
        "format": "wav",
        "segment_size": 30,
        "top_k": 5,
        "top_p": 1.0,
        "temperature": 1.0,
    })
    url = f"{BASE_URL}/voice/gpt-sovits?{params}"
    print(f"\n{'='*60}")
    print(f"[GPT-SoVITS TTS] text='{text}' id={speaker_id} lang={lang}")
    print(f"[GET] {url}")
    print(f"{'='*60}")

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as response:
            audio_data = response.read()
            with open(output_file, "wb") as f:
                f.write(audio_data)
            size_kb = len(audio_data) / 1024
            print(f"  [成功] 已保存到 {output_file} ({size_kb:.1f} KB)")
            return output_file
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [错误] HTTP {e.code}: {body}")
        return None
    except urllib.error.URLError as e:
        print(f"  [错误] {e}")
        return None


def check_speaker(model_type, speaker_id):
    """检查指定模型和说话人是否可用"""
    params = urllib.parse.urlencode({
        "model_type": model_type,
        "id": speaker_id,
    })
    url = f"{BASE_URL}/voice/check?{params}"
    print(f"\n{'='*60}")
    print(f"[CHECK] model={model_type} id={speaker_id}")
    print(f"[GET] {url}")
    print(f"{'='*60}")

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            print(f"  结果: {json.dumps(data, ensure_ascii=False)}")
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [错误] HTTP {e.code}: {body}")
        return None
    except urllib.error.URLError as e:
        print(f"  [错误] {e}")
        return None


def test_online_demo():
    """测试在线 Hugging Face Demo（无需本地部署）"""
    hf_base = "https://artrajz-vits-simple-api.hf.space"
    print(f"\n{'='*60}")
    print(f"[测试在线 Demo] {hf_base}")
    print(f"{'='*60}")

    # 获取说话人列表
    url = f"{hf_base}/voice/speakers"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            total = sum(len(speakers) for speakers in data.values())
            print(f"  在线 Demo 共有 {total} 个说话人")

            # 尝试合成一段语音
            text = "Hello, this is a test."
            params = urllib.parse.urlencode({"text": text, "id": 4})
            tts_url = f"{hf_base}/voice/vits?{params}"
            print(f"  正在合成: '{text}'...")

            req2 = urllib.request.Request(tts_url)
            with urllib.request.urlopen(req2, timeout=60) as resp:
                audio_data = resp.read()
                output_file = "output_online_demo.wav"
                with open(output_file, "wb") as f:
                    f.write(audio_data)
                size_kb = len(audio_data) / 1024
                print(f"  [成功] 已保存到 {output_file} ({size_kb:.1f} KB)")

    except urllib.error.URLError as e:
        print(f"  [错误] 在线 Demo 可能不可用: {e}")


def main():
    print("=" * 60)
    print("  vits-simple-api 接口调用示例")
    print(f"  服务地址: {BASE_URL}")
    print("=" * 60)

    # 1. 获取说话人列表
    speakers = get_speakers()

    if speakers is None:
        print("\n无法连接到本地服务。")
        print("你可以:")
        print("  1. 启动本地服务后重试")
        print("  2. 测试在线 Demo (输入 'y')")
        choice = input("\n是否测试在线 Demo? [y/N]: ").strip().lower()
        if choice == 'y':
            test_online_demo()
        return

    # 2. 获取默认参数
    get_default_parameters()

    # 3. 检查是否有可用的模型
    has_vits = len(speakers.get("VITS", [])) > 0
    has_bert_vits2 = len(speakers.get("BERT-VITS2", [])) > 0
    has_gpt_sovits = len(speakers.get("GPT-SOVITS", [])) > 0

    # 4. 根据可用模型进行 TTS 测试
    if has_vits:
        tts_vits("你好世界，这是一个语音合成测试。", speaker_id=0, lang="zh")
        check_speaker("VITS", 0)

    if has_bert_vits2:
        tts_bert_vits2("今天天气真不错，适合出去走走。", speaker_id=0, lang="zh")
        check_speaker("BERT-VITS2", 0)

    if has_gpt_sovits:
        tts_gpt_sovits("欢迎使用语音合成系统。", speaker_id=0, lang="zh")
        check_speaker("GPT-SOVITS", 0)

    if not (has_vits or has_bert_vits2 or has_gpt_sovits):
        print("\n[提示] 没有加载任何模型，无法进行 TTS 测试。")
        print("请将模型文件放入 data/models/ 目录后重启服务。")

    print(f"\n{'='*60}")
    print("  示例完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
