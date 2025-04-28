## 可转债多因子优化脚本


### 1. 运行脚本
```
./run_optimizer.sh -m single --trials 500
./run_optimizer.sh -m continuous --trials 200  

# 帮助
./run_optimizer.sh --help


```

### 2. 查看最佳模型
```
python view_best_model.py
```

### 3. 查看所有模型
```
python view_best_model.py --list
```

### 4. 查看指定模型
```
python view_best_model.py --model <model_path>
```


# 假设要创建 num=2,3,4,5 四个环境
for num in 1 2 3 4 5 6 7 8 9 10 ; do
  env_name="lude_100_150_hold5_fac3_num${num}"
  echo "▶️ 创建环境：${env_name}"
  conda create -n "${env_name}" python=3.12 -y
done

```
conda create --name lude_100_150_hold5_fac3_num1  python=3.12
conda activate lude_100_150_hold5_fac3_num1
./run_optimizer.sh -m continuous --method tpe --strategy multistage  --start 20220729 --end 20250328 --min 100 --max 150 --jobs 15 --trials 3000 --hold 5 --seed-start 42 --seed-step 1000 --iterations 10 --factors 3 

./run_optimizer.sh -m continuous --method tpe --strategy multistage  --start 20220729 --end 20250328 --min 100 --max 150 --jobs 15 --trials 3000 --hold 5 --seed-start 42 --seed-step 1000 --iterations 10 --factors 4 

# 查看状态
./run_optimizer.sh --status

# 停止
./run_optimizer.sh --stop
```



cd /root/autodl-tmp/lude_100_150_hold5_fac3_num1
git clone https://github.com/soulZhaoL/lude.git
git pull
cd /root/autodl-tmp/lude_100_150_hold5_fac3_num1/lude/optuna_search/new_test/
cp /root/*.pq /root/autodl-tmp/lude_100_150_hold5_fac3_num1/lude/optuna_search/new_test/

