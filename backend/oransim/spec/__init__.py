"""oransim.spec — idea → ProductSpec 编译管线.

单向依赖: spec/ → engine (data/, config/, agents/, ...).
引擎层禁止 import 本包任何模块 (REG-4).
"""
