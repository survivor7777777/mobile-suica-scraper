# mobile-suica-scraper

[English document](./README.md) is also available.d

モバイルSuicaのウェブ https://www.mobilesuica.com/ からデータを自動的に集めてくるスクリプト

## 何をするソフトウェアなの？

モバイルSuicaは電子マネーとして日本で広く使われています。
モバイルSuicaの利用者は利用履歴を電子的に取得したいところですが、
JRが運営しているMobile SuicaのWebページには(少し前時代的な)下記のようなCaptcha

![Mobile Suica Captcha Image](https://github.com/survivor7777777/mobile-suica-scraper/blob/master/sample-Captcha.gif?raw=true)  

がセットされていて、ロボットがデータにアクセスできないようになっています。

このスクリプトはCaptchaを解いてモバイルSuicaのWebから利用履歴を収集することができます。

## このソフトウェアを使うためには何をすればいいの？

以下の一連の作業を行います。
1. Captchaイメージの入手
1. Captchaイメージにアノテーションを付ける(事前学習されたCNNモデルを使って自動的に行い、その後GUIツールを使って手動で修正する)
1. 前処理した学習データからCNNモデルを構築する

これで準備完了。あとは何度でもロボットを使ってモバイルSuicaのウェブから利用明細のデータを取得することができます。

![The Process Flow](https://github.com/survivor7777777/mobile-suica-scraper/blob/master/process-flow.png?raw=true)

## ファイルの概要

* getcaptcha.pl: Mobile Suica web page から Captcha ファイルをダウンロードする Perl スクリプト
* prebuild-model/: 事前学習されたモデルが格納されているディレクトリ
* auto-annotate.py: ダウンロードされた Captcha ファイルに自動的にアノテーションをつける Python スクリプト
* annotate.py: 手動でアノテーションを編集する Python スクリプト
* ssd.py, extractor.py, multibox*.py: Chainer CNN model
* train.py: Mobile Suica の Captcha を解く CNN model を学習する Python スクリプト
* scrape.pl: 学習した CNN model を使って Mobile Suica Web Page からデータを読み取る Perl スクリプト
* solve.py: script.pl が Captcha を解くために呼びだす Python スクリプト

## 無保証

このソフトウェアは完全に無保証です。
学習目的での使用以外はできません。
自己責任で利用ください。

## 前提ソフトウェア

このソフトウェアは次のライブラリ類を使っています。

* Python 3
  * chainer
  * chainercv
  * numpy
  * scipy
  * opencv-python
  * matplotlib
  * Pillow
  * tkinter
* Perl
  * WWW::Mechanize
  * Web::Scraper
  * Time::HiRes
  * JSON
  * Getopt::Long
  * File::Path

## Python関連の前提ソフトウェアのインストール方法

`pip` を使ってインストールします。

    pip install chainer numpy scipy opencv-python matplotlib Pillow

`python`, `pyenv`, `pip` のインストール方法はググって調べてください。

## Perl関連の前提ソフトウェアのインストール方法

`cpan` を使ってインストールします。

    cpan WWW::Mechanize Web::Scraper Time::HiRes JSON Getopt::Long File::Path

`perl`, `pyenv`, `cpan` のインストール方法はググって調べてください。

## モデルの学習

自分でモデルを学習させたい場合は、この章の説明に従ってください。それが面倒な場合は、事前学習させたモデルが利用できます。単に以下のコマンドを実行して、次の章に進んでください。

    ln -s prebuild-model model

### 教師データとなるCaptchaイメージの入手

スクリプト `getcaptcha.pl` を次のように実行します。

    ./getcaptcha.pl --interval=500000 100

これにより、イメージを100枚webから500ミリ秒間隔で取得し、`./data` ディレクトリに保管します。
取得インターバルを短くしないでください。DOS攻撃とみなされるかもしれません。

### 自動でまたは手動でCaptchaイメージにアノテーションを付ける

スクリプト `auto-annotate.py` を以下のように実行すると、事前学習したCNNモデルを使って、ダウンロードしたCaptchaイメージにアノテーションが自動的につきます。

    ./auto-annotate.py

これによりファイル `./data/dataset.json` にアノテーションが書き込まれます。すでにアノテーションがついているファイルはスキップしますので、手動アノテーションと自動アノテーションを繰り返すことも可能です。

事前学習モデルの精度 100% ではありません。10% 前後の誤りが含まれます。したがって、自動でつけられたアノテーションはスクリプト `annotate.py` を使って、レビューして修正してください。

    ./annotate.py

これによりGUIウィンドウが開きます。対話的にアノテーションを編集することができます。

### アノテーションを付けたデータからCNNモデルを学習

スクリプト `train.py` を実行して、Captchaを解くCNNモデルを作成します。

    ./train.py

これは時間がかかります（マシンパワーによりますが、数100秒から数時間）。もしNVIDIAのGPUとcudaがインストールされているなら、`--gpu=0` オプションを付けると、GPU を使用するようになります。

この結果、`./model` ディレクトリにモデルが出力されます。

以上で学習が完了します。

## モバイルSuicaのデータを取得

### モバイルSuicaのパスワードを含むファイルを作成

ファイル `./credentials.json` を以下のような内容で作成します。

    {
      "user": "YOUR Mobile SUICA Account (E-Mail address)",
      "password": "YOUR Mobile SUICA Password"
    }

このファイルはパスワードを含むので、アクセス権を適切に設定してください。例えば、

    chmod 600 ./credentials.json

以上で準備ができました。

### モバイルSuicaのデータをCSVとして取得

ウェブ https://www.mobilesuica.com/ からモバイルSuicaのデータを取得するには、スクリプト `./scrape.pl` を実行します。

    ./scrape.pl

すると、利用明細が標準出力にCSV形式で出力されます。新しくダウンロードした captcha イメージは、data ディレクトリに追加されますので、モデルの追加学習に利用できます。`./log` ディレクトリにはログ情報が記録されます。

### モバイルSuicaのデータをDBに取得

もしデータベース (MySQL や SQLite) にデータを格納したいなら、ファイル `./dbi-config.json` を以下のような内容で作成します。

	{
	"driver": "DBIドライバ名 (ex. DBI:mysql, DBI:SQLite",
	"database": "データベース名",
	"user": "データベースユーザ名",
	"password": "データベースパスワード",
	"table": "テーブル名 (ex. expense"
	"options": { "RaiseError": 1, "PrintError": 0, "AutoCommit": 0 }
	}

このファイルもパスワードを含んでいるので、`chmod 600 ./dbi-config.json` などとして、他のユーザから読み取られないように設定します。

その上で　`./scrape.pl --db` を実行すると、スクレーピングしたデータをデータベースに格納します。

Enjoy!

## どういう仕組みになっているの?

[Single Shot Multibox Detector (SSD)](https://arxiv.org/abs/1512.02325) の考え方を真似ながら、ただし文字の大きさにはバリエーションがないと想定されることから、特定のスケーリングだけに検出器をおいたモデルになっています。

captcha は 175x60 のモノクロですし、使われている文字数は 33文字に限られるので、特徴量抽出は比較的小さい CNN モデルで実現できました。`extractor.py` をご覧ください。

抽出された特徴量は、`multibox.py` で定義されている CNN で、文字の bounding box の場所と大きさを検出しています。

