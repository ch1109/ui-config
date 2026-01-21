# app/api/v1/project.py
"""
项目管理 API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from app.database import get_db
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListItem
)
from app.models.project import Project
from app.models.page_config import PageConfig

router = APIRouter(prefix="/api/v1/projects", tags=["Project"])


@router.get("", response_model=List[ProjectListItem])
async def list_projects(db: AsyncSession = Depends(get_db)):
    """获取所有项目列表"""
    # 获取所有项目及其页面数量
    result = await db.execute(
        select(
            Project,
            func.count(PageConfig.id).label("page_count")
        )
        .outerjoin(PageConfig, PageConfig.project_id == Project.id)
        .group_by(Project.id)
        .order_by(Project.created_at.desc())
    )
    
    projects = []
    for row in result.all():
        project = row[0]
        page_count = row[1]
        projects.append(ProjectListItem(
            id=project.id,
            project_id=project.project_id,
            name=project.name,
            description=project.description,
            color=project.color or "#3b82f6",
            icon=project.icon or "folder",
            page_count=page_count,
            created_at=project.created_at
        ))
    
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个项目详情"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 ID {project_id} 不存在"
        )
    
    # 获取页面数量
    count_result = await db.execute(
        select(func.count(PageConfig.id)).where(PageConfig.project_id == project_id)
    )
    page_count = count_result.scalar() or 0
    
    return ProjectResponse(
        id=project.id,
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        color=project.color or "#3b82f6",
        icon=project.icon or "folder",
        page_count=page_count,
        created_at=project.created_at,
        updated_at=project.updated_at
    )


@router.post("", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新项目"""
    # 检查 project_id 是否重复
    result = await db.execute(
        select(Project).where(Project.project_id == project_data.project_id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"项目 ID '{project_data.project_id}' 已存在"
        )
    
    # 检查名称是否重复
    result = await db.execute(
        select(Project).where(Project.name == project_data.name)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"项目名称 '{project_data.name}' 已存在"
        )
    
    project = Project(
        project_id=project_data.project_id,
        name=project_data.name,
        description=project_data.description,
        color=project_data.color or "#3b82f6",
        icon=project_data.icon or "folder"
    )
    
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    return ProjectResponse(
        id=project.id,
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        color=project.color,
        icon=project.icon,
        page_count=0,
        created_at=project.created_at,
        updated_at=project.updated_at
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新项目信息"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 ID {project_id} 不存在"
        )
    
    # 检查名称是否与其他项目重复
    if project_data.name and project_data.name != project.name:
        name_check = await db.execute(
            select(Project).where(
                Project.name == project_data.name,
                Project.id != project_id
            )
        )
        if name_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"项目名称 '{project_data.name}' 已存在"
            )
    
    # 更新字段
    if project_data.name is not None:
        project.name = project_data.name
    if project_data.description is not None:
        project.description = project_data.description
    if project_data.color is not None:
        project.color = project_data.color
    if project_data.icon is not None:
        project.icon = project_data.icon
    
    await db.commit()
    await db.refresh(project)
    
    # 获取页面数量
    count_result = await db.execute(
        select(func.count(PageConfig.id)).where(PageConfig.project_id == project_id)
    )
    page_count = count_result.scalar() or 0
    
    return ProjectResponse(
        id=project.id,
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        color=project.color,
        icon=project.icon,
        page_count=page_count,
        created_at=project.created_at,
        updated_at=project.updated_at
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除项目（项目下的页面将取消关联，不会被删除）"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 ID {project_id} 不存在"
        )
    
    # 将项目下的页面取消关联
    await db.execute(
        PageConfig.__table__.update()
        .where(PageConfig.project_id == project_id)
        .values(project_id=None)
    )
    
    await db.delete(project)
    await db.commit()
    
    return {"success": True, "message": f"项目 '{project.name}' 已删除"}
