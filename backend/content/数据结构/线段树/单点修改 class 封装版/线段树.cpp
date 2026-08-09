class SegmentTree
{
private:
	struct Node {
		Node () {init();}
		Node (ll x) {sum = x;}
		ll sum;
		void init(){
			sum = 0;
		}
	};
	
	int n;
	vector <Node> tr;
	
	friend Node operator + (const Node A, const Node B){
		Node p;
		p.sum = A.sum + B.sum;
		return p;
	}
	int ls(int p) {return p << 1;}
	int rs(int p) {return p << 1 | 1;}
	void pull(int p){
		tr[p] = tr[ls(p)] + tr[rs(p)];
	}
	void modify(int x, ll k, int p, int l, int r){
		if(x > r || x < l) return;
		if(l == x && r == x){
			tr[p].sum += k; 
			return;
		}
		int mid = l + r >> 1;
		modify(x, k, ls(p), l, mid); modify(x, k, rs(p), mid + 1, r);
		pull(p);
	}
	Node query(int L, int R, int p, int l, int r){
		if(L > r || R < l) return Node();
		if(L <= l && R >= r) return tr[p];
		int mid = l + r >> 1;
		return query(L, R, ls(p), l, mid) + query(L, R, rs(p), mid + 1, r);
	}
	
public:
	SegmentTree (): n(0) {}
	SegmentTree (int _n, ll x){
		init(vector (_n + 1, x));
	}
	SegmentTree (vector <ll> vec){
		init(vec);
	}
	void init(vector <ll> vec){
		n = vec.size() - 1;
		tr.assign(4 << __lg(n), Node());
		auto build = [&](auto&& build, int p, int l, int r) -> void {
			if(l == r){
				assert(l <= n);
				tr[p] = Node(vec[l]);
				return;
			}
			int mid = l + r >> 1;
			build(build, ls(p), l, mid);
			build(build, rs(p), mid + 1, r);
			pull(p);
		};
		build(build, 1, 1, n);
	}
	void modify(int x, ll k) {modify(x, k, 1, 1, n);}
	Node query(int L, int R) {return query(L, R, 1, 1, n);}
};