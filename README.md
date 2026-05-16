4つのcsvファイルをマージするスクリプト

案件　NHT2602　用

ヘッダが同じデータ列は縦に、ヘッダが違う列は空白列を挿入して混在しないようにずらす

python merge_csv_colnum_args.py --a a.csv --b b.csv --c c.csv --d d.csv

左から　a,b,c,d　の並びになるようにマージ

idを昇順でソートして出力

ダミーデータ（idが1桁）は削除して出力
