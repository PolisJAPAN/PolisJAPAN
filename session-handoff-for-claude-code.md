# セッション引き継ぎ: 複数 GitHub アカウントのフォルダ別自動切り替え

このドキュメントは、別セッションで検討した内容を Claude Code に引き継ぐためのもの。
以下の背景・決定事項をふまえて、実装の実行を手伝ってほしい。

---

## やりたいこと（ゴール）

複数の会社から支給された **個人 GitHub アカウント**（組織アカウントではない）を、プロジェクトフォルダ単位で自動的に使い分けたい。

- `git commit` のコミット情報（`user.name` / `user.email`）がフォルダに応じて自動で切り替わる
- `git push` の認証鍵（＝どのアカウントか）もフォルダに応じて自動で切り替わる
- VSCode の Source Control、Claude Code のコマンド実行、どちらでも取り違えが起きない

---

## 決定した方式

以下の2段構えで実現する（この方針はすでに合意済み。実装に進んでよい）。

1. **コミット情報の切り替え**: 親 `~/.gitconfig` に `includeIf "gitdir:..."` を書き、フォルダ配下では会社別の子 gitconfig を読み込む
2. **認証鍵の切り替え**: `~/.ssh/config` でホストエイリアスを定義し、子 gitconfig の `insteadOf` で URL を書き換えて対応する鍵を使わせる

### 方式に関する重要な決定・理由

- **アカウントごとに別の SSH 鍵を作る**。GitHub は同じ公開鍵を複数アカウントに登録できないため、鍵の使い回しは不可。
- **`~/.ssh/config` の各 Host に `IdentitiesOnly yes` を必ず入れる**。これがないと、別会社の鍵で認証が通ってしまう取り違え事故が起きうる（複数個人アカウントで最もハマる落とし穴）。
- **`insteadOf` は子 gitconfig 側に書く**。こうするとそのフォルダ配下でのみ URL 書き換えが効き、グローバルに影響しない。
- **`gitdir:` のパスは末尾スラッシュ必須**（`~/work/company-a/`）。漏れるとサブディレクトリにマッチしない。
- **親 `~/.gitconfig` の `[user]` に `email` をあえて書かない**。設定漏れフォルダでコミット時にエラーになり、事故に気づける。
- **コミット用メール**は、対象アカウントに登録済みのアドレス（会社メール、または GitHub の `数字+username@users.noreply.github.com` 形式）を使う。Verified 表示とコントリビューション反映のために必要。
- **`gh`（GitHub CLI）は使わない**。VSCode の Source Control は内部でシステムの `git` を直接呼ぶため、本方式だけでフォルダ自動切り替えが効く。`gh` はフォルダ単位の切り替えができず取り違えリスクがあるので、認証の主役にはしない。

---

## 目標のファイル構成（会社A・会社Bの例）

```
~/
├── .gitconfig                  # 親。includeIf で子を振り分け
├── .gitconfig-company-a        # A社の user + insteadOf
├── .gitconfig-company-b        # B社の user + insteadOf
├── .ssh/
│   ├── config                  # ホスト別に鍵を振り分け（IdentitiesOnly yes）
│   ├── id_company_a (+ .pub)   # A社アカウントに登録
│   └── id_company_b (+ .pub)   # B社アカウントに登録
└── work/
    ├── company-a/              # A社リポジトリの置き場
    └── company-b/              # B社リポジトリの置き場
```

会社が3社以上なら同じパターンで増やす。

---

## 実装手順

### 1. フォルダ作成
```bash
mkdir -p ~/work/company-a ~/work/company-b
```

### 2. アカウントごとに SSH 鍵を生成
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_company_a -C "company-a account"
ssh-keygen -t ed25519 -f ~/.ssh/id_company_b -C "company-b account"
```

### 3. 公開鍵を各 GitHub アカウントに登録（手動）
```bash
cat ~/.ssh/id_company_a.pub   # → A社アカウントの Settings → SSH keys に登録
cat ~/.ssh/id_company_b.pub   # → B社アカウントに登録
```
※ 登録はブラウザ操作のためユーザー本人が行う。`.pub`（公開鍵）を登録すること。

### 4. `~/.ssh/config`
```
Host github-company-a
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_company_a
    IdentitiesOnly yes

Host github-company-b
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_company_b
    IdentitiesOnly yes
```
作成後 `chmod 600 ~/.ssh/config`。macOS なら各 Host に `AddKeysToAgent yes` / `UseKeychain yes` を足してもよい（任意）。

### 5. 親 `~/.gitconfig` に追記
```ini
[includeIf "gitdir:~/work/company-a/"]
    path = ~/.gitconfig-company-a
[includeIf "gitdir:~/work/company-b/"]
    path = ~/.gitconfig-company-b
```

### 6. 子 gitconfig を作成

`~/.gitconfig-company-a`:
```ini
[user]
    name = <A社で使う名前>
    email = <A社アカウントのメール>

[url "git@github-company-a:"]
    insteadOf = git@github.com:
```

`~/.gitconfig-company-b`:
```ini
[user]
    name = <B社で使う名前>
    email = <B社アカウントのメール>

[url "git@github-company-b:"]
    insteadOf = git@github.com:
```

### 7. SSH 接続テスト
```bash
ssh -T git@github-company-a
ssh -T git@github-company-b
```
→ `Hi <ユーザー名>!...` の名前が各社のアカウントになっているか確認。

### 8. クローンして検証
```bash
cd ~/work/company-a
git clone git@github.com:<A社org>/<repo>.git   # 通常URLでOK。自動で書き換わる
cd <repo>
git config --show-origin user.email   # A社メール & 由来ファイルを確認
git remote -v                          # github-company-a 経由になっているか確認
```

---

## Claude Code にお願いしたいこと

1. 上記手順のうち、**コマンドで完結する部分（1・2・4・5・6）を実行**してほしい。
   - ただし `~/.gitconfig`・`~/.ssh/config` は既存内容がある可能性があるので、**上書きではなく追記**し、実行前に現状を `cat` で確認すること。
2. **手動が必要な部分（3の公開鍵登録、8のクローン）は、案内だけ出して私が行う**。
3. 実行後、**Step 7・8の検証コマンドを走らせて結果を確認**してほしい。

### 実装前に私に確認してほしい項目

- 会社数（A・Bの2社でよいか、3社以上か）
- 各社の `user.name`（コミットに表示する名前）
- 各社の `user.email`（会社メール or noreply 形式のどちらか）
- クローン先フォルダ名の希望（`company-a` などでよいか、実際の会社名にするか）

これらが埋まれば、子 gitconfig の `<...>` を実値に置き換えて実装を進められる。

---

## 完了チェックリスト

- [ ] `~/work/company-a/` 配下で `git config user.email` がA社メールを返す
- [ ] `~/work/company-b/` 配下で `git config user.email` がB社メールを返す
- [ ] 各フォルダで `git remote -v` が `github-company-a` / `-b` 経由になっている
- [ ] `ssh -T git@github-company-a` / `-b` が各社ユーザー名を返す
- [ ] 各フォルダで test コミット → push が正しいアカウントで通る
- [ ] VSCode の Source Control 経由でも同じ結果になる（`gh` なしで動く）
