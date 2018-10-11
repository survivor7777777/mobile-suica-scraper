# mobile-suica-scraper

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
1. Captchaイメージにアノテーションを付ける(事前学習されたCNNモデルを使って自動的に行うか、GUIツールを使って手動で行う)
1. アノテーションに基づいてCaptchaデータを前処理して学習データに変換する
1. 前処理した学習データからCNNモデルを構築する

これで準備完了。あとは何度でもロボットを使ってモバイルSuicaのウェブから利用明細のデータを取得することができます。

![The Process Flow](https://github.com/survivor7777777/mobile-suica-scraper/blob/master/process-flow.png?raw=true)

## ファイルの概要

* getcaptcha.pl: Mobile Suica web page から Captcha ファイルをダウンロードする Perl スクリプト
* prebuild-model/: 事前学習されたモデルが格納されているディレクトリ
* auto-annotate.py: ダウンロードされた Captcha ファイルに自動的にアノテーションをつける Python スクリプト
* annotate.py: 手動でアノテーションを編集する Python スクリプト
* preprocess.py: アノテーションがつけられたデータから分割された学習データを作る　Python スクリプト
* model.py: Chainer CNN model
* train.py: Mobile Suica の Captcha を解く CNN model を学習する Python スクリプト
* scrape.pl: 学習した CNN model を使って Mobile Suica Web Page からデータを読み取る Perl スクリプト
* scrape-mysql.pl: scrape.pl と同様だが、取得したデータを MySQL データベースに格納する Perl スクリプト
* solve.py: script.pl が Captcha を解くために呼びだす Python スクリプト

# 無保証

このソフトウェアは完全に無保証です。
学習目的での使用以外はできません。
自己責任で利用ください。

# 前提ソフトウェア

このソフトウェアは次のライブラリ類を使っています。

* Python 3
  * chainer
  * numpy
  * scipy
  * opencv-python
  * matplotlib
  * Pillow
* Perl
  * WWW::Mechanize
  * Web::Scraper
  * Time::HiRes
  * JSON
  * Getopt::Long

## Python関連の前提ソフトウェアのインストール方法

"pip"を使ってインストールします。

    pip install chainer numpy scipy opencv-python matplotlib Pillow

"python", "pyenv", "pip"のインストール方法はググって調べてください。

## Perl関連の前提ソフトウェアのインストール方法

"cpan"を使ってインストールします。

    cpan WWW::Mechanize Web::Scraper Time::HiRes JSON Getopt::Long

"perl", "cpan"のインストール方法はググって調べてください。

# セットアップ方法

## Captchaイメージの入手

スクリプト "getcaptcha.pl" を次のように実行します。

    ./getcaptcha.pl --interval=500000 100

これにより、イメージを100枚webから500ミリ秒間隔で取得し、"./data" ディレクトリに保管します。
取得インターバルを短くしないでください。DOS攻撃とみなされるかもしれません。

## 自動でまたは手動でCaptchaイメージにアノテーションを付け

スクリプト "auto-annotate.py" を以下のように実行すると、事前学習したCNNモデルを使って、ダウンロードしたCaptchaイメージにアノテーションが自動的につきます。

    ./auto-annotate.py

これによりファイル "./data/dataset.json" にアノテーションが書き込まれます。

事前学習モデルの精度 100% ではありません。15-20%の誤りが含まれます。
したがって、自動でつけられたアノテーションはスクリプト "annotate.py" を使って、
レビューして修正してください。

    ./annotate.py

これによりGUIウィンドウが開きます。対話的にアノテーションを編集することができます。

## アノテーションつきイメージの前処理

スクリプト "preprocess.py" を実行して、アノテーションに基づき分割されたイメージデータを作成します。

    ./preprocess.py

この結果、"./segmented-data" ディレクトリに分割されたイメージが書き込まれます。

## 分割されたデータからCNNモデルを学習

スクリプト "train.py" を実行して、Captchaを解くCNNモデルを作成します。

    ./train.py

これは時間がかかります（マシンパワーによりますが、数100秒から数時間）。
もしNVIDIAのGPUとcudaがインストールされているなら、"--gpu=0" オプションを付けると、GPU を使用するようになります。

この結果、"./model" ディレクトリにモデルが出力されます。

## モバイルSuicaのパスワードを含むファイルを作成

ファイル "./credentials.json" を以下のような内容で作成します。

    {
      "user": "YOUR MOBILE SUICA E-Mail ADDRESS",
      "password": "YOUR MOBILE SUICA PASSWORD"
    }

このファイルはパスワードを含むので、アクセス権を適切に設定してください。例えば、

    chmod 600 ./credentials.json

以上で準備ができました。

# モバイルSuicaのデータを取得

ウェブ https://www.mobilesuica.com/ からモバイルSuicaのデータを取得するには、スクリプト "./scrape.pl" を実行します。

    ./scrape.pl

すると、利用明細が標準出力にCSV形式で出力されます。
"./log" ディレクトリにはログ情報が記録されます。

Enjoy!
