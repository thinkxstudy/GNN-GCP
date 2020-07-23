import os, sys
import random
import numpy as np
import json
from functools import reduce

class InstanceLoader(object):

    def __init__(self,path):
        self.path = path
        self.filenames = [ path + '/' + x for x in os.listdir(path) ]
        random.shuffle(self.filenames)
        self.reset()
    #end

    def get_instances(self, n_instances):
        for i in range(n_instances):
            # Read graph from file
            Ma,chrom_number,diff_edge = read_graph(self.filenames[self.index])
            f = self.filenames[self.index]
            
            Ma1 = Ma
            Ma2 = Ma.copy()

            if diff_edge is not None:
                # Create a (UNSAT/SAT) pair of instances with one edge of difference
                # The second instance has one edge more (diff_edge) which renders it SAT
                Ma2[diff_edge[0],diff_edge[1]] = Ma2[diff_edge[1],diff_edge[0]] =1
            #end

            # Yield both instances
            yield Ma1,chrom_number,f
            yield Ma2,chrom_number,f

            if self.index + 1 < len(self.filenames):
                self.index += 1
            else:
                self.reset()
        #end
    #end

    def get_new_instances(self):
        print(self.filenames[self.index])
        Ma,chrom_number = read_graph(self.filenames[self.index], True)
        f = self.filenames[self.index]
    
        yield Ma, chrom_number, f

        if self.index + 1 < len(self.filenames):
            self.index += 1
        else:
            self.reset()
    #end

    def create_batch(instances, newset=False):

        # n_instances: number of instances
        n_instances = len(instances)
        
        # n_vertices[i]: number of vertices in the i-th instance
        n_vertices  = np.array([ x[0].shape[0] for x in instances ])
        # n_edges[i]: number of edges in the i-th instance
        n_edges     = np.array([ len(np.nonzero(x[0])[0]) for x in instances ])
        # n_colors[i]: number of colors in the i-th instance
        n_colors = np.array( [x[1] for x in instances])
        # total_vertices: total number of vertices among all instances
        total_vertices  = sum(n_vertices)
        # total_edges: total number of edges among all instances
        total_edges     = sum(n_edges)
        # total_colors: total number of colors among all instances
        total_colors = sum(n_colors)

        # Compute matrices M, MC
        # M is the adjacency matrix
        M              = np.zeros((total_vertices,total_vertices))
        # MC is a matrix connecting each problem nodes to its colors candidates
        MC = np.zeros((total_vertices, total_colors))        

        # Even index instances are SAT, odd are UNSAT
        if newset==False:
            cn_exists = np.array([ 1-(i%2) for i in range(n_instances) ])
        else:
            cn_exists = np.array([ 1 for i in range(n_instances) ])

        for (i,(Ma,chrom_number,f)) in enumerate(instances):
            # Get the number of vertices (n) and edges (m) in this graph
            n, m, c = n_vertices[i], n_edges[i], n_colors[i]
            # Get the number of vertices (n_acc) and edges (m_acc) up until the i-th graph
            n_acc = sum(n_vertices[0:i])
            m_acc = sum(n_edges[0:i])
            c_acc = sum(n_colors[0:i])
            #Populate MC
            MC[n_acc:n_acc+n,c_acc:c_acc+c] = 1

            # Get the list of edges in this graph
            edges = list(zip(np.nonzero(Ma)[0], np.nonzero(Ma)[1]))

            # Populate M
            for e,(x,y) in enumerate(edges):
                if Ma[x,y] == 1:
                  M[n_acc+x,n_acc+y] = M[n_acc+y,n_acc+x] = 1
                #end if
            #end for
        #end for
        return M, n_colors, MC, cn_exists, n_vertices, n_edges, f
    #end


    def get_batches(self, batch_size):
        for i in range( len(self.filenames) // batch_size ):
            instances = list(self.get_instances(batch_size))
            yield InstanceLoader.create_batch(instances)
        #end
    #end
    
    def get_test_batches(self, batch_size, total_instances):
        for i in range( total_instances ):
            instances = list(self.get_instances(batch_size))
            yield InstanceLoader.create_batch(instances)
        #end
    #end

    def get_new_test_batches(self):
        for i in range( len(self.filenames) ):
            instances = list(self.get_new_instances())
            yield InstanceLoader.create_batch(instances, True)

    def reset(self):
        random.shuffle(self.filenames)
        self.index = 0
    #end
#end

def read_graph(filepath, newset=False):
    f = open(filepath,"r")

    # Select original/other dataset
    if newset==False:
        line = ''

        # Parse number of vertices
        while 'DIMENSION' not in line: line = f.readline();
        n = int(line.split()[1])
        Ma = np.zeros((n,n),dtype=int)
        
        # Parse edges
        while 'EDGE_DATA_SECTION' not in line: line = f.readline();
        line = f.readline()
        while '-1' not in line:
            i,j = [ int(x) for x in line.split() ]
            Ma[i,j] = 1
            line = f.readline()
        #end while

        # Parse diff edge
        while 'DIFF_EDGE' not in line: line = f.readline();
        diff_edge = [ int(x) for x in f.readline().split() ]

        # Parse target cost
        while 'CHROM_NUMBER' not in line: line = f.readline();
        chrom_number = int(f.readline().strip())
        return Ma,chrom_number,diff_edge
    else:
        chrom_number = Ma = None

        # read DIMACS format graph
        if not filepath[-4:] == '.json':
            for line in f:
                # skip comments & blank lines
                if line.startswith('c') or not line.strip():
                    continue
                # read header
                if line.startswith('p'):
                    print(line)
                    node_num = int(line.split()[2])
                    edge_num = int(line.split()[3])
                    Ma = np.zeros((node_num,node_num),dtype=int)
                # read edges
                if line.startswith('e'):
                    flist = line.split()
                    node_id = int(flist[1]) - 1
                    neigh_id = int(flist[2]) - 1
                    # ignore self-loop
                    if not node_id == neigh_id:
                        Ma[node_id, neigh_id] = 1
                        Ma[neigh_id, node_id] = 1
                # read chrom number
                if line.startswith ('h'):
                    chrom_number = int(line.split()[1])
        # read layout format graph
        else:
            f = open(filepath,'r')
            data = json.load(f)
            Ma = np.zeros((len(data),len(data)),dtype=int)
            for item in data:
                node_id = int(item['id'])
                for neighbor_item in item['conflict']:
                    neig_id = int(neighbor_item['id'])
                    Ma[node_id, neig_id] = Ma[neig_id, node_id] = 1
        if chrom_number is None:
            chrom_number = 10
        return Ma, chrom_number
        
#end
