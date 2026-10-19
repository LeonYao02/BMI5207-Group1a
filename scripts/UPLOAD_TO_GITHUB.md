# 手动推送 GitHub

本次没有替你推送。以下流程从远端重新 clone，避免使用旧的本地提交历史。
检查时远端仓库为空；如果组员随后提交了同名文件，复制前先比较，勿覆盖组员工作。

## 第一次上传

1. 把代码包解压到 Downloads，得到 `BMI5207_Person4_Code` 文件夹。
2. 在 Terminal 执行下面命令。`BMI5207-Group1a-upload` 需是尚不存在的新目录。

```bash
cd "$HOME/Downloads"
git clone https://github.com/LeonYao02/BMI5207-Group1a.git BMI5207-Group1a-upload
cd BMI5207-Group1a-upload
cp -R "$HOME/Downloads/BMI5207_Person4_Code/." .
git branch -M main
git add .github .gitignore README.md config docs mappings reports requirements.txt scripts src tests
git diff --cached --stat
git diff --cached --name-only
# 确认列表中只有代码、文档、映射和汇总报告，然后执行：
git commit -m "Complete Person 4 medication ETL for five patients"
git push -u origin main
```

GitHub 身份验证使用你本地的 GitHub 登录、SSH 或个人访问令牌；不要把密码/令牌写进代码。
若远端保护 main，改为 `git switch -c person4-medications` 后
`git push -u origin person4-medications`，再在 GitHub 建 PR。
若显示 non-fast-forward，先 `git fetch origin` 并比较变更，勿使用 `--force`。

## 在已有 checkout 中更新

先 `git status`，保留自己的未提交改动；工作区干净后 `git pull --ff-only`。
比较并复制本次文件，再使用上面的显式 `git add`、diff、commit 和 push。
不要直接把代码包覆盖进存在其他组员未提交文件的目录。

## 私密结果包如何用

私密包的 `private/` 和 `outputs/` 可复制到本地仓库根目录，用于查看和组内整合。
这些目录以及原始 Excel 都被忽略，不会进入以上显式 add 列表。
不要推 `group_key.hex`、原始患者/Case_No 对照、日期偏移、源文件名审计或患者级结果。
提交包含的是汇总验证报告；患者级 CSV 通过课程允许的私密方式交付。
旧的单患者示例和旧 63 位编号已被本次全量版本替代，不要混用。
