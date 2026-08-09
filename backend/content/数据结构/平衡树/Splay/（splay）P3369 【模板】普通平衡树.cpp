#include<bits/stdc++.h>
#define inf 0x3f3f3f3f
#define maxn 500050
#define maxm 500050 
#define vi vector <int>
#define vvi vector <vi>
#define endl '\n'
#define ll long long
using namespace std;

int son[maxn][2], fa[maxn], siz[maxn], val[maxn], cnt[maxn];
int root, tot;

void push_up(int x)
{
	siz[x] = siz[son[x][0]] + siz[son[x][1]] + cnt[x];
}

bool checkson(int x)
{
	return (son[fa[x]][1] == x);
}

void clean(int x)
{
	son[x][0] = son[x][1] = cnt[x] = siz[x] = fa[x] = val[x] = 0;
}

void rorate(int x)
{
	int f = fa[x], gf = fa[f], chk = checkson(x); //checkson: 0 为左儿子，1 为右儿子
	//下注释以右旋为例（即 chk = 0)
	son[f][chk] = son[x][chk ^ 1]; //将 f 的左儿子设为 x 的右儿子
	if(son[x][chk ^ 1]) fa[son[x][chk ^ 1]] = f; //如果 x 右儿子存在，将其 fa 设为 f
	son[x][chk ^ 1] = f; //将 x 右儿子设为 f
	fa[f] = x; //将 f 的 fa 设为 x
	fa[x] = gf; //将 x 的 fa 设为 gf
	if(gf) son[gf][f == son[gf][1]] = x; //如果 gf 存在，将 gf 中 f 原来占的儿子位置设为 x
	push_up(f); push_up(x); //pushup 维护
}

void splay(int x)
{
	for(int f = fa[x]; (f = fa[x]) != 0; rorate(x)){
		if(fa[f]) rorate(checkson(x) == checkson(f) ? f : x);
	}
	root = x;
}

void ins(int k)
{ 
	if(!root){
		root = ++ tot;
		val[tot] = k, siz[tot] = cnt[tot] = 1;
		return;
	}
	int f = 0, cur = root;
	while(1){
		if(val[cur] == k){
			cnt[cur] ++;
			push_up(cur), push_up(f);
			splay(cur);
			break;
		}
		f = cur, cur = son[cur][val[cur] < k];
		if(!cur){
			val[++ tot] = k;
			siz[tot] = cnt[tot] = 1;
			fa[tot] = f, son[f][val[f] < k] = tot;
			push_up(f);
			splay(tot);
			break;
		}
	}
}

int query_rank(int k)
{
	int res = 0, cur = root;
	while(1){
		if(!cur) return res + 1;
		if(val[cur] > k){
			cur = son[cur][0];
		}
		else{
			res += siz[son[cur][0]];
			if(val[cur] == k){
				splay(cur);
				return res + 1;
			}
			res += cnt[cur];
			cur = son[cur][1];
		}
	}
}

int query_num(int k)
{
	int cur = root;
	while(1){
		if(siz[son[cur][0]] >= k){
			cur = son[cur][0];
		}
		else{
			k -= siz[son[cur][0]] + cnt[cur];
			if(k <= 0){
				splay(cur);
				return val[cur];
			}
			cur = son[cur][1];
		}
	}
}

int pre()
{
	int cur = son[root][0];
	while(son[cur][1]) cur = son[cur][1];
	return cur;
}

int suf()
{
	int cur = son[root][1];
	while(son[cur][0]) cur = son[cur][0];
	return cur;
}

void del(int k)
{
	int qwq = query_rank(k); //调用一次 queryrank，将要删的数旋至根结点
	if(cnt[root] > 1){
		cnt[root] --, siz[root] --;
		return;
	}
	if(!son[root][0] && !son[root][1]){
		clean(root);
		root = 0;
		return;
	}
	if(!son[root][0]){
		int cur = root;
		root = son[root][1];
		fa[root] = 0;
		clean(cur);
		return;
	}
	if(!son[root][1]){
		int cur = root;
		root = son[root][0];
		fa[root] = 0;
		clean(cur);
		return;
	}
	int cur = root; 
	int newroot = pre(); //如果要删的数左右儿子都存在，那么将其的前驱作为新根
	splay(newroot);
	fa[son[cur][1]] = root;
	son[root][1] = son[cur][1];
	clean(cur);
	push_up(root);
}

int query_pre(int k)
{
	ins(k);
	int res = pre();
	del(k);
	return val[res];
}

int query_suf(int k)
{
	ins(k);
	int res = suf();
	del(k);
	return val[res];
}

void solve()
{
	int n; cin >> n;
	for(int i = 1; i <= n; i ++){
		int op, k; cin >> op >> k;
		switch (op){
		case 1:
			ins(k);
			break;
		case 2:
			del(k);
			break;
		case 3:
			cout << query_rank(k) << endl;
			break;
		case 4:
			cout << query_num(k) << endl;
			break;
		case 5:
			cout << query_pre(k) << endl;
			break;
		case 6:
			cout << query_suf(k) << endl;
			break;
		}
	}
}

int main()
{
	ios::sync_with_stdio(false);
	cin.tie(0); //cout.tie(0);
	
	int t = 1;
	//cin >> t; 
	while(t --) solve();
	
	return 0;
}
