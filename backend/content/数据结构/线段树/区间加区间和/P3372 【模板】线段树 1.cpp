#include<bits/stdc++.h>
#define inf 0x3f3f3f3f
#define maxn 100005
#define endl '\n'
#define ll long long
using namespace std;

int n, m;
ll sum[maxn << 2], tag[maxn << 2], a[maxn];

int ls(int p) {return p << 1;}
int rs(int p) {return p << 1 | 1;}

void push_up(int p)
{
	sum[p] = sum[ls(p)] + sum[rs(p)];
}

void build(int p, int l, int r)
{
	if(l == r) {sum[p] = a[l]; return;}
	int mid = (l + r) >> 1;
	build(ls(p), l, mid);
	build(rs(p), mid + 1, r);
	push_up(p);
}

void f(int p, int l, int r, ll k)
{
	tag[p] += k;
	sum[p] += (r - l + 1) * k;
}

void push_down(int p, int l, int r)
{
	int mid = (l + r) >> 1;
	f(ls(p), l, mid, tag[p]);
	f(rs(p), mid + 1, r, tag[p]);
	tag[p] = 0;
}

void update(int ul, int ur, int p, int l, int r, ll k)
{
	if(ul <= l && ur >= r) //lazy tag. Zzz...
	{
		f(p, l, r, k);
		return;
	}
	push_down(p, l, r); //��˯�ˣ����ѡ�
	int mid = (l + r) >> 1;
	if(mid >= ul) update(ul, ur, ls(p), l, mid, k);
	if(mid < ur) update(ul, ur, rs(p), mid + 1, r, k);
	push_up(p);
}

ll query(int ql, int qr, int p, int l, int r)
{
	ll res = 0;
	if(ql <= l && qr >= r) return sum[p];
	push_down(p, l, r);
	int mid = (l + r) >> 1;
	if(mid >= ql) res += query(ql, qr, ls(p), l, mid);
	if(mid < qr) res += query(ql, qr, rs(p), mid + 1, r);
	return res;
}

int main()
{
	ios::sync_with_stdio(false);
	cin.tie(0); cout.tie(0);
	
	cin >> n >> m;
	for(int i = 1; i <= n; i ++) cin >> a[i];
	build(1, 1, n);

	for(int i = 1; i <= m; i ++)
	{
		int op; cin >> op;
		if(op == 1)
		{
			int x, y; ll k; cin >> x >> y >> k;
			update(x, y, 1, 1, n, k);
		}
		else if(op == 2)
		{
			int x, y; cin >> x >> y;
			cout << query(x, y, 1, 1, n) << endl;
		}
	}
	
	return 0;
}
