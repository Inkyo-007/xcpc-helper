#include<bits/stdc++.h>
#define inf 0x3f3f3f3f
#define maxn 100050
#define maxm 500050 
#define vi vector <int>
#define vvi vector <vi>
#define endl '\n'
#define ll long long
using namespace std;

struct Treap
{
	int val, ord, ls, rs, siz, cnt;
} tree[maxn]; int tot;
#define val(x) tree[x].val
#define ord(x) tree[x].ord
#define ls(x) tree[x].ls
#define rs(x) tree[x].rs
#define siz(x) tree[x].siz
#define cnt(x) tree[x].cnt

void push_up(int x)
{
	siz(x) = siz(ls(x)) + siz(rs(x)) + cnt(x);
}

void rrotate(int &p) //右旋
{
	int tmp = ls(p);
	ls(p) = rs(tmp), rs(tmp) = p;
	siz(tmp) = siz(p);
	push_up(p);
	p = tmp;
}

void lrotate(int &p) //左旋
{
	int tmp = rs(p);
	rs(p) = ls(tmp), ls(tmp) = p;
	siz(tmp) = siz(p);
	push_up(p);
	p = tmp;
}

void _add(int &p, int k)
{
	if(!p){
		p = ++ tot;
		siz(p) = cnt(p) = 1, val(p) = k;
		ord(p) = rand();
		return;
	}
	siz(p) ++;
	if(val(p) == k) cnt(p) ++;
	else if(val(p) > k){
		_add(ls(p), k);
		if(ord(p) > ord(ls(p))) rrotate(p);
	}
	else{
		_add(rs(p), k);
		if(ord(p) > ord(rs(p))) lrotate(p);
	}
}

void _del(int &p, int k)
{
	if(!p) return;
	if(val(p) == k){
		if(cnt(p) > 1){
			cnt(p) --, siz(p) --;
			return;
		}
		if(!ls(p) || !rs(p)){
			p = ls(p) + rs(p);
			return;
		}
		else if(ord(ls(p)) < ord(rs(p))){
			rrotate(p);
			_del(p, k);
		}
		else{
			lrotate(p);
			_del(p, k);
		}
	}
	else{
		if(val(p) < k){
			_del(rs(p), k);
			siz(p) --;
		}
		else{
			_del(ls(p), k);
			siz(p) --;
		}
	}
}

int query_rank(int p, int k) //查询 k 的排名
{
	if(!p) return 1;
	if(k < val(p)) return query_rank(ls(p), k);
	else if(k > val(p)) return siz(ls(p)) + cnt(p) + query_rank(rs(p), k);
	else return siz(ls(p)) + 1;
}

int query_num(int p, int k) //查询排名为 k 的数
{
	if(!p) return 0;
	if(k <= siz(ls(p))) return query_num(ls(p), k);
	else if(k > siz(ls(p)) + cnt(p)) return query_num(rs(p), k - siz(ls(p)) - cnt(p));
	else return val(p);
}

int query_pre(int p, int k)
{
	int res = -1;
	while(p){
		if(val(p) < k) res = val(p), p = rs(p);
		else p = ls(p);
	}
	return res;
}

int query_suf(int p, int k)
{
	int res = -1;
	while(p){
		if(val(p) > k) res = val(p), p = ls(p);
		else p = rs(p);
	}
	return res;
}

void solve()
{
	int n; cin >> n;
	int root = 0;
	for(int i = 1; i <= n; i ++){
		int op, k; cin >> op >> k;
		switch (op){
		case 1:
			_add(root, k);
			break;
		case 2:
			_del(root, k);
			break;
		case 3:
			cout << query_rank(root, k) << endl;
			break;
		case 4:
			cout << query_num(root, k) << endl;
			break;
		case 5:
			cout << query_pre(root, k) << endl;
			break;
		case 6:
			cout << query_suf(root, k) << endl;
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
