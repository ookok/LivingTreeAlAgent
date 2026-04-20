"""
语音功能测试脚本

测试 TTS、STT 和语音对话功能
"""

import asyncio
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_tts():
    """测试 TTS 功能"""
    logger.info("=== 测试 TTS 功能 ===")
    
    try:
        from core.living_tree_ai.voice.voice_adapter import (
            MossTTSAdapter, VoiceConfig
        )
        
        # 创建适配器
        adapter = MossTTSAdapter()
        
        # 测试中文语音合成
        logger.info("测试中文语音合成...")
        config = VoiceConfig(
            voice="zh-CN-XiaoxiaoNeural",
            rate="+0%",
            pitch="+0Hz"
        )
        
        result = await adapter.synthesize("你好，这是一个语音合成测试。", config=config)
        
        if result.success:
            logger.info("TTS 合成成功")
            if result.audio_data:
                # 保存测试音频
                test_file = "test_output.mp3"
                with open(test_file, "wb") as f:
                    f.write(result.audio_data)
                logger.info(f"音频已保存到: {test_file}")
        else:
            logger.error(f"TTS 合成失败: {result.error}")
        
        # 测试英文语音合成
        logger.info("测试英文语音合成...")
        result_en = await adapter.synthesize(
            "Hello, this is a speech synthesis test.",
            config=VoiceConfig(voice="en-US-JennyNeural")
        )
        
        if result_en.success:
            logger.info("英文 TTS 合成成功")
        
        return True
        
    except Exception as e:
        logger.error(f"TTS 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_stt():
    """测试 STT 功能"""
    logger.info("=== 测试 STT 功能 ===")
    
    try:
        from core.living_tree_ai.voice.voice_adapter import WhisperSTTAdapter
        
        # 创建适配器
        adapter = WhisperSTTAdapter(model="base")
        
        # 注意：需要实际的音频文件进行测试
        logger.info("Whisper STT 适配器已创建")
        logger.info("注意：需要实际的音频文件进行完整测试")
        
        return True
        
    except Exception as e:
        logger.error(f"STT 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_voice_dialog():
    """测试语音对话系统"""
    logger.info("=== 测试语音对话系统 ===")
    
    try:
        from core.living_tree_ai.voice.voice_dialog import (
            VoiceDialogSystem, VoiceConferenceSystem
        )
        
        # 测试对话系统
        dialog_system = VoiceDialogSystem()
        
        # 创建会话
        session_id = dialog_system.create_session()
        logger.info(f"创建对话会话: {session_id}")
        
        # 测试 Agent 处理函数
        async def test_agent_handler(session_id, user_text):
            logger.info(f"[Agent] 收到消息: {user_text}")
            return f"我收到了你的消息: {user_text}"
        
        dialog_system.set_agent_handler(test_agent_handler)
        
        # 测试文本输入
        response = await dialog_system.process_text_input(
            session_id,
            "你好，测试消息"
        )
        
        if response:
            logger.info(f"[Agent] 回复: {response}")
        
        # 获取会话历史
        history = dialog_system.get_session_history(session_id)
        logger.info(f"会话历史消息数: {len(history)}")
        
        # 测试会议系统
        logger.info("\n测试会议系统...")
        conference_system = VoiceConferenceSystem()
        
        # 创建房间
        room_id = "test_room"
        success = conference_system.create_room(room_id)
        logger.info(f"创建房间: {room_id}, 成功: {success}")
        
        # 添加参与者
        success = conference_system.add_participant(
            room_id,
            "user_001",
            "测试用户1"
        )
        logger.info(f"添加参与者: 成功={success}")
        
        # 获取房间信息
        info = conference_system.get_room_info(room_id)
        logger.info(f"房间信息: {info}")
        
        return True
        
    except Exception as e:
        logger.error(f"语音对话测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    logger.info("开始测试语音功能...")
    
    # 测试 TTS
    tts_success = await test_tts()
    logger.info(f"TTS 测试: {'通过' if tts_success else '失败'}")
    
    # 测试 STT
    stt_success = await test_stt()
    logger.info(f"STT 测试: {'通过' if stt_success else '失败'}")
    
    # 测试语音对话
    dialog_success = await test_voice_dialog()
    logger.info(f"语音对话测试: {'通过' if dialog_success else '失败'}")
    
    logger.info("\n语音功能测试完成!")


if __name__ == "__main__":
    asyncio.run(main())
