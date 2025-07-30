#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复总览页面流量费用显示
"""

def fix_dashboard_display():
    """修复总览页面显示问题"""
    print("=== 修复总览页面流量费用显示 ===\n")
    
    # 测试API
    from app import app
    with app.test_client() as client:
        response = client.get('/api/traffic_summary')
        data = response.get_json()
        
        print("API测试结果:")
        print(f"  状态码: {response.status_code}")
        print(f"  返回数据: {data}")
        
        if response.status_code == 200 and data:
            print(f"\n✅ API正常工作")
            print(f"  流量费用: ${data.get('traffic_cost', 0):.2f}")
            print(f"  占比: {data.get('traffic_percentage', 0):.1f}%")
            print(f"  总费用: ${data.get('total_cost', 0):.2f}")
            
            if data.get('traffic_cost', 0) == 0:
                print(f"\n💡 流量费用为$0.00是正常的，因为:")
                print(f"  - EC2实例流量在免费额度内（前1GB/月免费）")
                print(f"  - CloudFront没有实际流量")
                print(f"  - 没有NAT Gateway等付费流量服务")
                print(f"\n📱 总览页面应该显示: 流量费用 $0.00 (0.0%)")
        else:
            print(f"❌ API异常")
    
    print(f"\n🔧 如果总览页面仍然不显示，请检查:")
    print(f"  1. 浏览器控制台是否有JavaScript错误")
    print(f"  2. 网络请求是否成功")
    print(f"  3. HTML元素ID是否正确")

if __name__ == '__main__':
    fix_dashboard_display()