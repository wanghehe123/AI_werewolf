"""
统一 API 响应格式
=================
采用经典的 code/message/data 结构返回 API 响应。

响应格式：
- code: 业务状态码（0=成功，其他=错误）
- message: 描述信息
- data: 实际数据（可选）

使用方式：
    from ai_werewolf.api.responses import success_response, error_response

    @router.get("/items")
    def list_items() -> dict:
        items = ["a", "b", "c"]
        return success_response(data=items)

    @router.get("/error")
    def raise_error() -> dict:
        return error_response(message="资源不存在", code=404)
"""

from typing import Any


def success_response(data: Any = None, message: str = "ok", code: int = 0) -> dict:
    """
    构建成功响应的标准格式

    Args:
        data: 响应数据，可为任意类型
        message: 成功描述信息，默认 "ok"
        code: 业务状态码，默认 0 表示成功

    Returns:
        统一格式的响应字典
    """
    return {
        "code": code,
        "message": message,
        "data": data,
    }


def error_response(message: str = "error", code: int = 1, data: Any = None) -> dict:
    """
    构建错误响应的标准格式

    Args:
        message: 错误描述信息
        code: 业务错误码，非 0 值表示错误
        data: 错误详情（可选）

    Returns:
        统一格式的错误响应字典
    """
    return {
        "code": code,
        "message": message,
        "data": data,
    }