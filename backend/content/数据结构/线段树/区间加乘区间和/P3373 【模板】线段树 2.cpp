#include<bits/stdc++.h>
#define inf 0x3f3f3f3f
#define maxn 100005
#define endl '\n'
#define ll long long
using namespace std;

int n, q, m;
ll ans[maxn << 2], tagadd[maxn << 2], tagmul[maxn << 2], a[maxn];

int ls(int p) {return p << 1;}
int rs(int p) {return p << 1 | 1;}

void push_up(int p)
{
	ans[p] = (ans[ls(p)] + ans[rs(p)]) % m;
}

void build(int p, int l, int r)
{
	tagadd[p] = 0; tagmul[p] = 1;
	if(l == r) {ans[p] = a[l]; return;}
	int mid = (l + r) >> 1;
	build(ls(p), l, mid);
	build(rs(p), mid + 1, r);
	push_up(p);
}

void f(int p, int l, int r, ll kadd, ll kmul) 
{
	tagadd[p] = (tagadd[p] * kmul + kadd) % m;
	tagmul[p] = tagmul[p] * kmul % m;
	ans[p] = (ans[p] * kmul + (r - l + 1) * kadd) % m;
}

void push_down(int p, int l, int r)
{
	int mid = (l + r) >> 1;
	f(ls(p), l, mid, tagadd[p], tagmul[p]);
	f(rs(p), mid + 1, r, tagadd[p], tagmul[p]);
	tagadd[p] = 0; tagmul[p] = 1;
}

void update(int ul, int ur, int p, int l, int r, ll kadd, ll kmul)
{
	if(ul <= l && ur >= r) //lazy tag. Zzz...
	{
		f(p, l, r, kadd, kmul);
		return;
	}
	push_down(p, l, r); //��˯�ˣ����ѡ�
	int mid = (l + r) >> 1;
	if(mid >= ul) update(ul, ur, ls(p), l, mid, kadd, kmul);
	if(mid < ur) update(ul, ur, rs(p), mid + 1, r, kadd, kmul);
	push_up(p);
}

ll query(int ql, int qr, int p, int l, int r)
{
	ll res = 0;
	if(ql <= l && qr >= r) return ans[p] % m;
	push_down(p, l, r);
	int mid = (l + r) >> 1;
	if(mid >= ql) res += query(ql, qr, ls(p), l, mid);
	if(mid < qr) res += query(ql, qr, rs(p), mid + 1, r);
	return res % m;
}

int main()
{
	ios::sync_with_stdio(false);
	cin.tie(0); cout.tie(0);
	
	cin >> n >> q >> m;
	
	for(int i = 1; i <= n; i ++) cin >> a[i];
	build(1, 1, n);
	
	for(int i = 1; i <= q; i ++)
	{
		int op; cin >> op;
		if(op == 1)
		{
			int x, y; ll k; cin >> x >> y >> k;
			update(x, y, 1, 1, n, 0, k);
		}
		else if(op == 2)
		{
			int x, y; ll k; cin >> x >> y >> k;
			update(x, y, 1, 1, n, k, 1);
		}
		else if(op == 3)
		{
			int x, y; cin >> x >> y;
			cout << query(x, y, 1, 1, n) << endl;
		}
	}
	
	return 0;
}
