# app/api/v1/button.py
"""
按钮配置管理 API
提供按钮的增删改查功能，支持多语言
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models.button import Button
from app.schemas.button import (
    ButtonCreate, ButtonUpdate, ButtonResponse, 
    ButtonListResponse, ButtonOptionItem
)

router = APIRouter(prefix="/api/v1/buttons", tags=["Buttons"])

# 预设按钮数据（首次启动时初始化）
PRESET_BUTTONS = [
    # 操作按钮
    {"button_id": "confirm", "name": {"zh-CN": "确认", "en": "Confirm"}, "category": "operation"},
    {"button_id": "cancel", "name": {"zh-CN": "取消", "en": "Cancel"}, "category": "operation"},
    {"button_id": "previous_page", "name": {"zh-CN": "上一页", "en": "Previous Page"}, "category": "operation"},
    {"button_id": "next_page", "name": {"zh-CN": "下一页", "en": "Next Page"}, "category": "operation"},
    {"button_id": "print", "name": {"zh-CN": "打印", "en": "Print"}, "category": "operation"},
    {"button_id": "exit", "name": {"zh-CN": "退出", "en": "Exit"}, "category": "operation"},
    # 功能按钮
    {"button_id": "take_photo", "name": {"zh-CN": "拍照", "en": "Take Photo"}, "category": "function"},
    {"button_id": "retake", "name": {"zh-CN": "重拍", "en": "Retake"}, "category": "function"},
    {"button_id": "search", "name": {"zh-CN": "搜索", "en": "Search"}, "category": "function"},
    {"button_id": "check_authorization", "name": {"zh-CN": "勾选授权", "en": "Check Authorization"}, "category": "function"},
    {"button_id": "fingerprint_authorization", "name": {"zh-CN": "指纹授权", "en": "Fingerprint Authorization"}, "category": "function"},
    {"button_id": "forgot_password", "name": {"zh-CN": "忘记密码", "en": "Forgot Password"}, "category": "function"},
    {"button_id": "correct_password", "name": {"zh-CN": "更正密码", "en": "Correct Password"}, "category": "function"},
    # 导航按钮
    {"button_id": "return_home", "name": {"zh-CN": "返回首页", "en": "Return Home"}, "category": "navigation"},
    {"button_id": "next_step", "name": {"zh-CN": "下一步", "en": "Next Step"}, "category": "navigation"},
    {"button_id": "previous_step", "name": {"zh-CN": "上一步", "en": "Previous Step"}, "category": "navigation"},
    # 输入触发按钮
    {"button_id": "input_password", "name": {"zh-CN": "输入密码", "en": "Input Password"}, "category": "input_trigger"},
    {"button_id": "click_signature", "name": {"zh-CN": "点击签名", "en": "Click Signature"}, "category": "input_trigger"},
    {"button_id": "signature_modify_confirm", "name": {"zh-CN": "签名修改/确认", "en": "Signature Modify/Confirm"}, "category": "input_trigger"},
    {"button_id": "click_search", "name": {"zh-CN": "点击搜索", "en": "Click Search"}, "category": "input_trigger"},
    {"button_id": "click_authorization", "name": {"zh-CN": "点击授权", "en": "Click Authorization"}, "category": "input_trigger"},
]


async def init_preset_buttons(db: AsyncSession):
    """初始化预设按钮（仅在表为空时执行）"""
    result = await db.execute(select(Button).limit(1))
    if result.scalar_one_or_none() is not None:
        return  # 已有数据，不再初始化
    
    for btn_data in PRESET_BUTTONS:
        button = Button(
            button_id=btn_data["button_id"],
            name=btn_data["name"],
            description={},
            response_info={},
            voice_keywords=[],
            category=btn_data.get("category", "operation"),
            is_preset=True
        )
        db.add(button)
    
    await db.commit()


@router.get("", response_model=ButtonListResponse)
async def list_buttons(
    category: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    获取所有按钮列表
    
    可选参数:
    - category: 按分类筛选 (operation/function/navigation/input_trigger/selection)
    """
    # 确保预设按钮已初始化
    await init_preset_buttons(db)
    
    query = select(Button).order_by(Button.category, Button.button_id)
    
    if category:
        query = query.where(Button.category == category)
    
    result = await db.execute(query)
    buttons = result.scalars().all()
    
    # 构建响应
    button_responses = []
    options = []
    
    for btn in buttons:
        button_responses.append(ButtonResponse(
            id=btn.id,
            button_id=btn.button_id,
            name=btn.name or {},
            description=btn.description or {},
            response_info=btn.response_info or {},
            voice_keywords=btn.voice_keywords or [],
            category=btn.category or "operation",
            is_preset=btn.is_preset,
            created_at=btn.created_at,
            updated_at=btn.updated_at
        ))
        
        # 构建下拉选项
        zh_name = btn.name.get("zh-CN", btn.button_id) if isinstance(btn.name, dict) else btn.button_id
        options.append(ButtonOptionItem(
            value=btn.button_id,
            label=f"{zh_name} ({btn.button_id})",
            name=btn.name or {},
            description=btn.description or {},
            category=btn.category or "operation"
        ))
    
    return ButtonListResponse(
        success=True,
        total=len(buttons),
        buttons=button_responses,
        options=options
    )


@router.get("/options/list", response_model=List[ButtonOptionItem])
async def get_button_options(db: AsyncSession = Depends(get_db)):
    """
    获取按钮选项列表（用于下拉选择）
    
    返回简化的选项格式，适合前端下拉框使用
    """
    # 确保预设按钮已初始化
    await init_preset_buttons(db)
    
    result = await db.execute(
        select(Button).order_by(Button.category, Button.button_id)
    )
    buttons = result.scalars().all()
    
    options = []
    for btn in buttons:
        zh_name = btn.name.get("zh-CN", btn.button_id) if isinstance(btn.name, dict) else btn.button_id
        options.append(ButtonOptionItem(
            value=btn.button_id,
            label=f"{zh_name} ({btn.button_id})",
            name=btn.name or {},
            description=btn.description or {},
            category=btn.category or "operation"
        ))
    
    return options


@router.get("/{button_id}", response_model=ButtonResponse)
async def get_button(button_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个按钮详情"""
    result = await db.execute(
        select(Button).where(Button.button_id == button_id)
    )
    button = result.scalar_one_or_none()
    
    if not button:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"按钮 '{button_id}' 不存在"
        )
    
    return ButtonResponse(
        id=button.id,
        button_id=button.button_id,
        name=button.name or {},
        description=button.description or {},
        response_info=button.response_info or {},
        voice_keywords=button.voice_keywords or [],
        category=button.category or "operation",
        is_preset=button.is_preset,
        created_at=button.created_at,
        updated_at=button.updated_at
    )


@router.post("", response_model=ButtonResponse, status_code=status.HTTP_201_CREATED)
async def create_button(
    button_data: ButtonCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    创建新按钮
    
    按钮 ID 必须唯一，只能包含字母、数字和下划线
    """
    # 验证 button_id 格式
    if not button_data.button_id.replace("_", "").isalnum():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="按钮 ID 只能包含字母、数字和下划线"
        )
    
    # 检查是否已存在
    result = await db.execute(
        select(Button).where(Button.button_id == button_data.button_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"按钮 ID '{button_data.button_id}' 已存在"
        )
    
    # 验证名称
    if not button_data.name.get("zh-CN"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="按钮名称（简体中文）为必填项"
        )
    
    # 创建按钮
    button = Button(
        button_id=button_data.button_id,
        name=button_data.name,
        description=button_data.description or {},
        response_info=button_data.response_info or {},
        voice_keywords=button_data.voice_keywords or [],
        category=button_data.category or "operation",
        is_preset=False
    )
    
    db.add(button)
    await db.commit()
    await db.refresh(button)
    
    return ButtonResponse(
        id=button.id,
        button_id=button.button_id,
        name=button.name or {},
        description=button.description or {},
        response_info=button.response_info or {},
        voice_keywords=button.voice_keywords or [],
        category=button.category or "operation",
        is_preset=button.is_preset,
        created_at=button.created_at,
        updated_at=button.updated_at
    )


@router.put("/{button_id}", response_model=ButtonResponse)
async def update_button(
    button_id: str,
    button_data: ButtonUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    更新按钮信息
    
    预设按钮也可以更新（如添加描述、语音关键词等）
    """
    result = await db.execute(
        select(Button).where(Button.button_id == button_id)
    )
    button = result.scalar_one_or_none()
    
    if not button:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"按钮 '{button_id}' 不存在"
        )
    
    # 更新字段
    if button_data.name is not None:
        if not button_data.name.get("zh-CN"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="按钮名称（简体中文）为必填项"
            )
        button.name = button_data.name
    
    if button_data.description is not None:
        button.description = button_data.description
    
    if button_data.response_info is not None:
        button.response_info = button_data.response_info
    
    if button_data.voice_keywords is not None:
        button.voice_keywords = button_data.voice_keywords
    
    if button_data.category is not None:
        button.category = button_data.category
    
    await db.commit()
    await db.refresh(button)
    
    return ButtonResponse(
        id=button.id,
        button_id=button.button_id,
        name=button.name or {},
        description=button.description or {},
        response_info=button.response_info or {},
        voice_keywords=button.voice_keywords or [],
        category=button.category or "operation",
        is_preset=button.is_preset,
        created_at=button.created_at,
        updated_at=button.updated_at
    )


@router.delete("/{button_id}")
async def delete_button(button_id: str, db: AsyncSession = Depends(get_db)):
    """
    删除按钮
    
    注意：预设按钮不可删除
    """
    result = await db.execute(
        select(Button).where(Button.button_id == button_id)
    )
    button = result.scalar_one_or_none()
    
    if not button:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"按钮 '{button_id}' 不存在"
        )
    
    if button.is_preset:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="预设按钮不可删除"
        )
    
    await db.delete(button)
    await db.commit()
    
    return {"success": True, "message": f"按钮 '{button_id}' 已删除"}
