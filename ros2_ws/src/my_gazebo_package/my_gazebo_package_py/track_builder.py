import numpy as np

def calculate_boundaries(path_points, track_width=5.0, sample_dist=1.0, closed=True):
    """
    Calculates inner and outer boundaries for a given path.
    """
    path_points = np.array(path_points)
    num_points = len(path_points)
    
    # Resample path if needed (linear interpolation)
    full_path_x = []
    full_path_y = []
    
    iterations = num_points if closed else num_points - 1
    for i in range(iterations):
        p1 = path_points[i]
        p2 = path_points[(i + 1) % num_points]
        dist = np.linalg.norm(p2 - p1)
        if dist < 1e-6: continue
        num_samples = int(np.ceil(dist / sample_dist))
        
        for j in range(num_samples):
            t = j / num_samples
            p = p1 * (1 - t) + p2 * t
            full_path_x.append(p[0])
            full_path_y.append(p[1])
            
    if not closed:
        full_path_x.append(path_points[-1][0])
        full_path_y.append(path_points[-1][1])
        
    path_x = np.array(full_path_x)
    path_y = np.array(full_path_y)
    num_path_points = len(path_x)
    
    inner_cones = []
    outer_cones = []
    
    for i in range(num_path_points):
        p = np.array([path_x[i], path_y[i]])
        
        if closed:
            p_prev = np.array([path_x[(i - 1) % num_path_points], path_y[(i - 1) % num_path_points]])
            p_next = np.array([path_x[(i + 1) % num_path_points], path_y[(i + 1) % num_path_points]])
        else:
            if i == 0:
                p_prev = p
                p_next = np.array([path_x[i+1], path_y[i+1]])
            elif i == num_path_points - 1:
                p_prev = np.array([path_x[i-1], path_y[i-1]])
                p_next = p
            else:
                p_prev = np.array([path_x[i-1], path_y[i-1]])
                p_next = np.array([path_x[i+1], path_y[i+1]])
                
        # Tangent vector
        tangent = (p_next - p) + (p - p_prev)
        if np.linalg.norm(tangent) < 1e-6:
            # Fallback if tangent is zero
            if i < num_path_points - 1:
                tangent = np.array([path_x[i+1], path_y[i+1]]) - p
            else:
                tangent = p - np.array([path_x[i-1], path_y[i-1]])
                
        norm_tangent = np.linalg.norm(tangent)
        if norm_tangent > 1e-6:
            tangent /= norm_tangent
        else:
            tangent = np.array([1.0, 0.0])
            
        # Normal vector
        normal = np.array([-tangent[1], tangent[0]])
        
        # Inner and outer points
        p_inner = p - (track_width / 2.0) * normal
        p_outer = p + (track_width / 2.0) * normal
        
        inner_cones.append((float(p_inner[0]), float(p_inner[1])))
        outer_cones.append((float(p_outer[0]), float(p_outer[1])))
        
    return inner_cones, outer_cones

def generate_random_track(num_points=12, radius_min=15, radius_max=30, track_width=6.0, sample_dist=2.0):
    """
    Generates a random closed track path and its cone boundaries.
    """
    angles = np.linspace(0, 2*np.pi, num_points, endpoint=False)
    angles += np.random.uniform(-0.1, 0.1, num_points)
    angles.sort()
    
    radii = np.random.uniform(radius_min, radius_max, num_points)
    
    x = radii * np.cos(angles)
    y = radii * np.sin(angles)
    
    points = list(zip(x, y))
    return calculate_boundaries(points, track_width=track_width, sample_dist=sample_dist, closed=True)

if __name__ == "__main__":
    inner, outer = generate_random_track()
    print(f"Generated {len(inner)} inner cones and {len(outer)} outer cones.")
