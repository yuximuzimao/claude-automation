# 魔兽世界任务路线

面向国服泰坦重铸“时光”服的五开任务路线项目。Questie提供任务依赖和坐标基础数据，路线骨架负责顺序，实测层记录个人拾取、逐号点击、跟随卡点和地形修正。

## 当前成果

- Questie v11.32.3 Lua数据库解析器；
- ZIP或已解压Questie目录读取；
- 血精灵圣骑士逐日岛候选全清路线V1；
- 五开任务类型与待验证项；
- Questie人物历程脱敏导出说明。

## 生成路线

在项目目录运行：

```bash
python3 cli.py build-sunstrider \
  --questie-source ../_sandbox/wow-quest-route/Questie.zip
```

也可以把`--questie-source`指向已解压的`Questie`插件目录。

输出：

```text
data/routes/horde/blood-elf/sunstrider-isle-v1.md
data/routes/horde/blood-elf/sunstrider-isle-v1.json
```

## 测试

```bash
python3 -m unittest discover -s tests
```

## 实测反馈

正常过程不需要逐任务截图。只记录异常：

```text
步骤号｜任务名｜发生了什么｜五号中几号完成｜是否走回头路/卡跟随
```

人物历程导出见`docs/JOURNEY_EXPORT.md`。
