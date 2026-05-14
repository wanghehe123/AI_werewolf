from ai_werewolf.storage.models import RoleMetadata


def default_role_metadata() -> list[RoleMetadata]:
    return [
        RoleMetadata(role_key="werewolf", name="狼人", faction="wolf", description="夜晚共同袭击一名玩家", night_action=True),
        RoleMetadata(role_key="seer", name="预言家", faction="good", description="每晚查验一名玩家阵营", night_action=True),
        RoleMetadata(role_key="witch", name="女巫", faction="good", description="拥有解药和毒药", night_action=True),
        RoleMetadata(role_key="hunter", name="猎人", faction="good", description="出局时可开枪带走一名玩家", night_action=False),
        RoleMetadata(role_key="villager", name="平民", faction="good", description="无技能，好人阵营基础角色", night_action=False),
        RoleMetadata(role_key="guard", name="守卫", faction="good", description="每晚守护一名玩家", night_action=True),
        RoleMetadata(role_key="idiot", name="白痴", faction="good", description="被放逐后可翻牌免死但失去投票权", night_action=False),
        RoleMetadata(role_key="wolf_king", name="狼王", faction="wolf", description="出局时可带走一名玩家", night_action=True),
        RoleMetadata(role_key="knight", name="骑士", faction="good", description="白天可决斗质疑一名玩家", night_action=False),
        RoleMetadata(role_key="wolf_beauty", name="狼美人", faction="wolf", description="夜晚魅惑玩家，死亡时带走魅惑目标", night_action=True),
    ]
