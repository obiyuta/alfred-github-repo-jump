# alfred-github-repo-jump

[English](README.md) | 日本語

Alfred ワークフロー。`gh <名前>` と打つだけで、アクセスできる GitHub リポジトリに一発で飛ぶ。

リポジトリ一覧は認証済みの [`gh` CLI](https://cli.github.com/)（`gh api user/repos`）経由で取得するので、private リポ・所属 organization のリポ・collaborator として招待されたリポがすべて候補に出る。トークンの設定は不要。`gh` の既定ホストが GitHub Enterprise ならそちらでも動く。

## インストール

1. GitHub CLI をインストールしてログインする: `brew install gh && gh auth login`
2. [最新リリース](https://github.com/obiyuta/alfred-github-repo-jump/releases/latest)から `GitHub-Repo-Jump.alfredworkflow` をダウンロードして開く。

リポジトリをクローンした場合は `./install.sh` で Alfred の設定ディレクトリにコピーできる。

Alfred 5（Powerpack）と `/usr/bin/python3` が必要。後者は Xcode Command Line Tools を入れると使える（`xcode-select --install`。Homebrew を入れていれば導入済み）。

## 使い方

| キーワード | 動作 |
| --- | --- |
| `gh <クエリ>` | リポジトリをあいまい検索。`⏎` でリポジトリを開く |
| `⌘⏎` | Pull Requests を開く |
| `⌥⏎` | Issues を開く |
| `⌃⏎` | Actions を開く |
| `⇧⏎` | SSH clone URL をコピー |
| `ghr` | リポジトリ一覧のキャッシュを今すぐ更新 |

キャッシュの更新はターミナルから `repo_jump.py` を直接叩かず `ghr` で行う。Alfred はキャッシュの場所を `$alfred_workflow_cache` で渡すので、手動実行では別の場所に書かれてしまう。

並び順: 完全一致、前方一致、部分一致、owner の一致、複数語がすべて含まれる、説明文の一致、部分列（あいまい）一致の順。クエリはリポジトリ名と照合し、`/` を含むときは `owner/name` と照合する。同順位は最終 push が新しい順。

Alfred は選択履歴も学習し、学習は上の並び順より優先される。入力に対してよく選ぶリポジトリは、完全一致より上でも先頭に来るようになる。Alfred は入力途中の文字列でも学習するので、`doc` まで打った時点で選んだ結果が `docs` の並びにも影響しうる。表示は最大 500 件。学習はリポジトリの改名や移管をしても引き継がれる。リセットは Alfred の Preferences > Advanced > Clear Knowledge から行う。

末尾の行からは常に GitHub 上でクエリを検索できる（アクセス権のないリポジトリを探すとき用）。`Tab` で `owner/name` まで補完する。

## 仕組み

リポジトリ一覧は `gh api user/repos --paginate` で一度だけ取得し、Alfred のワークフロー用キャッシュディレクトリに保存する。検索はキャッシュだけを読むので即座に結果が出る。キャッシュが設定した TTL（デフォルト 6 時間）より古くなると、古い一覧をそのまま返しつつバックグラウンドで再取得する。

## 設定

Alfred のワークフロー設定画面から変更できる。

- **Cache TTL (hours)**: キャッシュを新しいとみなす時間。
- **Include archived**: アーカイブ済みリポジトリも候補に含める（デフォルトでは非表示）。

## ライセンス

MIT
